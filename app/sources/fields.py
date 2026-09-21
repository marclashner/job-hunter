"""Shared field mapping for board adapters. Deterministic; no LLM."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.models.enums import EmploymentType, RemotePolicy, Seniority

logger = logging.getLogger(__name__)

_TITLE_SENIORITY: tuple[tuple[str, Seniority], ...] = (
    ("distinguished", Seniority.DISTINGUISHED),
    ("principal", Seniority.PRINCIPAL),
    ("staff", Seniority.STAFF),
    ("senior", Seniority.SENIOR),
    ("sr.", Seniority.SENIOR),
    ("sr ", Seniority.SENIOR),
    ("junior", Seniority.JUNIOR),
    ("jr.", Seniority.JUNIOR),
    ("jr ", Seniority.JUNIOR),
    ("intern", Seniority.JUNIOR),
)


def as_string(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def as_job_id(payload: dict[str, Any]) -> str | None:
    raw = payload.get("id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def clip(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    return value[:max_length]


def seniority_from_title(title: str) -> Seniority | None:
    lowered = f" {title.lower()} "
    for needle, seniority in _TITLE_SENIORITY:
        if needle in lowered:
            return seniority
    return None


def remote_policy_from_text(*parts: str | None) -> RemotePolicy:
    blob = " ".join(part for part in parts if part).lower()
    if not blob:
        return RemotePolicy.UNKNOWN
    if "hybrid" in blob:
        return RemotePolicy.HYBRID
    if "remote" in blob:
        return RemotePolicy.REMOTE
    if "on-site" in blob or "onsite" in blob or "on site" in blob:
        return RemotePolicy.ONSITE
    return RemotePolicy.ONSITE


def employment_from_text(value: str | None) -> EmploymentType | None:
    if not value:
        return None
    lowered = value.lower()
    if "contract" in lowered:
        return EmploymentType.CONTRACT
    if "part" in lowered:
        return EmploymentType.PART_TIME
    if "full" in lowered:
        return EmploymentType.FULL_TIME
    return None


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC)
        except (OSError, OverflowError, ValueError):
            logger.warning("Ignoring unparsable epoch timestamp %s", value)
            return None
    raw = as_string(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Ignoring unparsable timestamp %s", raw)
        return None
