"""HTTP schemas for job-source sync."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import JobSource


class SourceSyncError(BaseModel):
    source_job_id: str | None = None
    reason: str


class SourceSyncResult(BaseModel):
    source: JobSource
    company_identifier: str
    fetched: int = Field(ge=0)
    inserted: int = Field(ge=0)
    updated: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: list[SourceSyncError] = Field(default_factory=list)
