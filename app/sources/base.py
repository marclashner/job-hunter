"""Shared job-source adapter contract for Greenhouse, Lever, Ashby, and later boards."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.models.enums import JobSource
from app.schemas.job import JobCreate


class RawJob(BaseModel):
    """Untyped payload from a board API, plus enough context to normalize it."""

    source: JobSource
    company_identifier: str = Field(min_length=1)
    company_name: str = Field(min_length=1)
    payload: dict[str, Any]


class JobNormalizationError(ValueError):
    """Raised when a raw listing cannot be mapped onto JobCreate."""


class JobSourceFetchError(RuntimeError):
    """Raised when the remote board cannot be read at all."""


class JobBoardNotFoundError(JobSourceFetchError):
    """Raised when the company/board identifier does not exist."""


class JobSourceAdapter(Protocol):
    """Board adapter (Greenhouse, Lever, Ashby, ...). No HTML scraping, no LLM."""

    def fetch_jobs(self, company_identifier: str) -> list[RawJob]:
        """Return raw listings. Skip individual malformed rows; do not raise for them."""

    def normalize(self, raw_job: RawJob) -> JobCreate:
        """Map one raw listing to the canonical create schema."""


__all__ = [
    "JobBoardNotFoundError",
    "JobNormalizationError",
    "JobSourceAdapter",
    "JobSourceFetchError",
    "RawJob",
]
