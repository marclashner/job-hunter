"""Deterministic work-eligibility countries from location strings."""

from __future__ import annotations

import re

_SPLIT = re.compile(r"[;/|&]+|,|\bor\b|\band\b", re.I)
_NON_GEO = re.compile(r"[^a-z0-9\s]+")

_COUNTRY_ALIASES: dict[str, str] = {
    "us": "US",
    "usa": "US",
    "u s": "US",
    "u s a": "US",
    "united states": "US",
    "united states of america": "US",
    "america": "US",
    "uk": "GB",
    "u k": "GB",
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    "canada": "CA",
    "germany": "DE",
    "deutschland": "DE",
    "netherlands": "NL",
    "holland": "NL",
    "ireland": "IE",
    "republic of ireland": "IE",
    "india": "IN",
    "australia": "AU",
    "poland": "PL",
    "france": "FR",
    "spain": "ES",
    "italy": "IT",
    "portugal": "PT",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "switzerland": "CH",
    "austria": "AT",
    "belgium": "BE",
    "singapore": "SG",
    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",
    "brazil": "BR",
    "mexico": "MX",
    "israel": "IL",
    "uae": "AE",
    "united arab emirates": "AE",
    "qatar": "QA",
    "saudi arabia": "SA",
    "kenya": "KE",
    "nigeria": "NG",
    "south africa": "ZA",
    "new zealand": "NZ",
    "philippines": "PH",
    "emea": "EMEA",
    "apac": "APAC",
    "latam": "LATAM",
}

_PLACE_TO_COUNTRY: dict[str, str] = {
    "san francisco": "US",
    "sf": "US",
    "new york": "US",
    "nyc": "US",
    "brooklyn": "US",
    "manhattan": "US",
    "seattle": "US",
    "austin": "US",
    "boston": "US",
    "denver": "US",
    "chicago": "US",
    "los angeles": "US",
    "la": "US",
    "washington": "US",
    "washington dc": "US",
    "dc": "US",
    "oakland": "US",
    "palo alto": "US",
    "mountain view": "US",
    "sunnyvale": "US",
    "redwood city": "US",
    "san mateo": "US",
    "san jose": "US",
    "portland": "US",
    "miami": "US",
    "atlanta": "US",
    "dallas": "US",
    "houston": "US",
    "phoenix": "US",
    "raleigh": "US",
    "durham": "US",
    "boulder": "US",
    "salt lake city": "US",
    "minneapolis": "US",
    "detroit": "US",
    "philadelphia": "US",
    "pittsburgh": "US",
    "honolulu": "US",
    "omaha": "US",
    "colorado springs": "US",
    "st louis": "US",
    "saint louis": "US",
    "london": "GB",
    "manchester": "GB",
    "edinburgh": "GB",
    "cambridge": "GB",
    "oxford": "GB",
    "amsterdam": "NL",
    "berlin": "DE",
    "munich": "DE",
    "dublin": "IE",
    "toronto": "CA",
    "vancouver": "CA",
    "montreal": "CA",
    "ottawa": "CA",
    "bangalore": "IN",
    "bengaluru": "IN",
    "hyderabad": "IN",
    "pune": "IN",
    "mumbai": "IN",
    "delhi": "IN",
    "sydney": "AU",
    "melbourne": "AU",
    "singapore": "SG",
    "tokyo": "JP",
    "doha": "QA",
    "riyadh": "SA",
    "dubai": "AE",
    "warsaw": "PL",
    "krakow": "PL",
}

_US_STATES: dict[str, str] = {
    "al": "US",
    "ak": "US",
    "az": "US",
    "ar": "US",
    "ca": "US",
    "co": "US",
    "ct": "US",
    "de": "US",
    "fl": "US",
    "ga": "US",
    "hi": "US",
    "id": "US",
    "il": "US",
    "in": "US",
    "ia": "US",
    "ks": "US",
    "ky": "US",
    "la": "US",
    "me": "US",
    "md": "US",
    "ma": "US",
    "mi": "US",
    "mn": "US",
    "ms": "US",
    "mo": "US",
    "mt": "US",
    "ne": "US",
    "nv": "US",
    "nh": "US",
    "nj": "US",
    "nm": "US",
    "ny": "US",
    "nc": "US",
    "nd": "US",
    "oh": "US",
    "ok": "US",
    "or": "US",
    "pa": "US",
    "ri": "US",
    "sc": "US",
    "sd": "US",
    "tn": "US",
    "tx": "US",
    "ut": "US",
    "vt": "US",
    "va": "US",
    "wa": "US",
    "wv": "US",
    "wi": "US",
    "wy": "US",
    "dc": "US",
    "california": "US",
    "colorado": "US",
    "florida": "US",
    "georgia": "US",
    "illinois": "US",
    "massachusetts": "US",
    "michigan": "US",
    "minnesota": "US",
    "new jersey": "US",
    "new york": "US",
    "north carolina": "US",
    "oregon": "US",
    "pennsylvania": "US",
    "texas": "US",
    "virginia": "US",
    "washington": "US",
}

_SKIP = frozenset(
    {
        "remote",
        "hybrid",
        "onsite",
        "on site",
        "office",
        "worldwide",
        "global",
        "anywhere",
        "multiple",
        "locations",
        "location",
        "within",
        "based",
        "open",
        "role",
    }
)


def parse_eligible_countries(location: str | None) -> list[str]:
    """Return ISO-like country codes implied by a job location string."""

    if not location or not location.strip():
        return []
    found: set[str] = set()
    normalized = location.replace("\u2013", "-").replace("\u2014", "-")
    chunks = [chunk.strip() for chunk in _SPLIT.split(normalized) if chunk.strip()]
    if not chunks:
        chunks = [normalized]
    for chunk in chunks:
        found.update(_codes_in_chunk(chunk))
    found.update(_codes_in_chunk(normalized))
    return sorted(code for code in found if code)


def preferred_country_codes(preferred_locations: list[str]) -> set[str]:
    codes: set[str] = set()
    for item in preferred_locations:
        codes.update(parse_eligible_countries(item))
    return codes


def _codes_in_chunk(chunk: str) -> set[str]:
    text = _NON_GEO.sub(" ", chunk.lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text or text in _SKIP:
        return set()
    codes: set[str] = set()
    for alias, code in sorted(_COUNTRY_ALIASES.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(alias)}\b", text):
            codes.add(code)
    for place, code in sorted(_PLACE_TO_COUNTRY.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{re.escape(place)}\b", text):
            codes.add(code)
    tokens = text.split()
    for token in tokens:
        if token in _US_STATES and len(token) > 2:
            codes.add("US")
    for abbr in re.findall(r"(?:^|[,;/(\s])\s*([A-Z]{2})\b", chunk):
        if abbr.lower() in _US_STATES:
            codes.add("US")
    return codes
