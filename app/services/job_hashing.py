"""Stable hashing so duplicate job descriptions can be detected."""

from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")


def normalize_job_description(description: str) -> str:
    return _WHITESPACE.sub(" ", description).strip().lower()


def job_content_hash(description: str) -> str:
    canonical = normalize_job_description(description)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
