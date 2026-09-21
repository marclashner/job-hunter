"""Deterministic compensation extraction from posting text. No LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PAY_HINT = re.compile(
    r"salary|compensation|pay transparency|base pay|pay range|annual cash|"
    r"total rewards|on-target earnings|ote\b",
    re.I,
)
_RANGE = re.compile(
    r"""
    (?P<cur>USD|CAD|GBP|EUR|AUD|\$|£|€)?
    \s*
    (?P<min>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,6}(?:\.\d+)?)
    \s*(?P<mink>[kK])?
    \s*(?:-|[\u2013\u2014]|to)\s*
    (?P<cur2>USD|CAD|GBP|EUR|AUD|\$|£|€)?
    \s*
    (?P<max>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,6}(?:\.\d+)?)
    \s*(?P<maxk>[kK])?
    (?:\s*(?P<unit>per\s+year|/year|annually|a year|per\s+hour|/hr|hourly))?
    """,
    re.I | re.X,
)
_SINGLE = re.compile(
    r"""
    (?P<cur>USD|CAD|GBP|EUR|AUD|\$|£|€)
    \s*
    (?P<amt>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,3}(?:\.\d+)?)
    \s*(?P<k>[kK])?
    \s*(?P<unit>per\s+year|/year|annually|a year|per\s+hour|/hr|hourly)?
    """,
    re.I | re.X,
)

_CURRENCY = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "USD": "USD",
    "CAD": "CAD",
    "GBP": "GBP",
    "EUR": "EUR",
    "AUD": "AUD",
}


@dataclass(frozen=True, slots=True)
class ParsedCompensation:
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    quote: str
    ambiguous: bool = False
    needs_llm: bool = False


def looks_like_pay_discussion(text: str) -> bool:
    return bool(_PAY_HINT.search(text) or "$" in text or "£" in text or "€" in text)


def parse_compensation(*parts: str | None) -> ParsedCompensation | None:
    blob = " ".join(part for part in parts if part)
    if not blob:
        return None
    matches = [_from_range(match) for match in _RANGE.finditer(blob)]
    matches = [item for item in matches if item is not None]
    if not matches:
        singles = [_from_single(match) for match in _SINGLE.finditer(blob)]
        matches = [item for item in singles if item is not None]
    if not matches:
        if looks_like_pay_discussion(blob):
            return ParsedCompensation(
                salary_min=None,
                salary_max=None,
                salary_currency="USD",
                quote="",
                needs_llm=True,
            )
        return None
    ranked = sorted(matches, key=lambda item: -_score(item, blob))
    best = ranked[0]
    competing = [
        item
        for item in ranked[1:]
        if item.salary_currency == best.salary_currency
        and _amount(item) is not None
        and _amount(best) is not None
        and abs((_amount(item) or 0) - (_amount(best) or 0)) > 15000
    ]
    us_best = next((item for item in ranked if _prefers_us(item, blob)), None)
    chosen = us_best or best
    ambiguous = bool(competing) and us_best is None
    return ParsedCompensation(
        salary_min=chosen.salary_min,
        salary_max=chosen.salary_max,
        salary_currency=chosen.salary_currency,
        quote=chosen.quote,
        ambiguous=ambiguous,
        needs_llm=ambiguous,
    )


def compensation_from_metadata(metadata: object) -> ParsedCompensation | None:
    if not isinstance(metadata, list):
        return None
    chunks: list[str] = []
    for item in metadata:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        value = item.get("value")
        if value is None or value == "" or value == 0:
            continue
        if re.search(r"salary|comp|pay|wage|midpoint|range", name, re.I):
            chunks.append(f"{name}: {value}")
    if not chunks:
        return None
    return parse_compensation(" ".join(chunks))


def _from_range(match: re.Match[str]) -> ParsedCompensation | None:
    currency = _currency(match.group("cur") or match.group("cur2"))
    minimum = _number(match.group("min"), match.group("mink"))
    maximum = _number(match.group("max"), match.group("maxk"))
    if minimum is None or maximum is None:
        return None
    minimum, maximum = _annualize(minimum, maximum, match.group("unit"))
    if not _plausible(minimum, maximum):
        return None
    return ParsedCompensation(
        salary_min=minimum,
        salary_max=maximum,
        salary_currency=currency,
        quote=match.group(0).strip(),
    )


def _from_single(match: re.Match[str]) -> ParsedCompensation | None:
    amount = _number(match.group("amt"), match.group("k"))
    if amount is None:
        return None
    annual, _ = _annualize(amount, amount, match.group("unit"))
    if not _plausible(annual, annual):
        return None
    return ParsedCompensation(
        salary_min=annual,
        salary_max=None,
        salary_currency=_currency(match.group("cur")),
        quote=match.group(0).strip(),
    )


def _number(raw: str | None, k_flag: str | None) -> int | None:
    if not raw:
        return None
    value = float(raw.replace(",", ""))
    if k_flag:
        value *= 1000
    if value > 10_000_000:
        return None
    return round(value)


def _annualize(minimum: int, maximum: int, unit: str | None) -> tuple[int, int]:
    lowered = (unit or "").lower()
    if "hour" in lowered or "/hr" in lowered:
        return minimum * 2080, maximum * 2080
    return minimum, maximum


def _plausible(minimum: int, maximum: int) -> bool:
    if minimum > maximum:
        return False
    if maximum < 20000 or minimum < 15:
        return False
    if maximum > 2_000_000:
        return False
    return True


def _currency(raw: str | None) -> str:
    if not raw:
        return "USD"
    return _CURRENCY.get(raw.upper() if raw.isalpha() else raw, "USD")


def _score(parsed: ParsedCompensation, blob: str) -> int:
    idx = blob.find(parsed.quote) if parsed.quote else -1
    window = blob[max(0, idx - 80) : idx + len(parsed.quote) + 80] if idx >= 0 else blob[:160]
    score = 0
    if re.search(r"base pay|salary|compensation|pay transparency|pay range", window, re.I):
        score += 5
    if re.search(r"united states|\busa\b|\bus\b", window, re.I):
        score += 4
    if re.search(r"standard cost of living|us remote", window, re.I):
        score += 3
    if parsed.salary_currency == "USD":
        score += 2
    if re.search(r"\b(uk|gbp|canada|cad|emea)\b", window, re.I):
        score -= 2
    return score


def _prefers_us(parsed: ParsedCompensation, blob: str) -> bool:
    idx = blob.find(parsed.quote) if parsed.quote else -1
    window = blob[max(0, idx - 100) : idx + len(parsed.quote) + 100] if idx >= 0 else ""
    return bool(re.search(r"united states|\busa\b|\bus\b|standard cost of living", window, re.I))


def _amount(parsed: ParsedCompensation) -> int | None:
    if parsed.salary_min is not None and parsed.salary_max is not None:
        return (parsed.salary_min + parsed.salary_max) // 2
    return parsed.salary_min or parsed.salary_max
