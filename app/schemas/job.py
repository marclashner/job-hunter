"""Pydantic v2 schemas for job ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import EmploymentType, HumanDecision, JobSource, RemotePolicy, Seniority


class JobCreate(BaseModel):
    source: JobSource = JobSource.MANUAL
    source_job_id: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    location: str | None = Field(default=None, max_length=255)
    remote_policy: RemotePolicy | None = None
    employment_type: EmploymentType | None = None
    seniority: Seniority | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    job_url: str | None = Field(default=None, max_length=2048)
    application_url: str | None = Field(default=None, max_length=2048)
    department: str | None = Field(default=None, max_length=255)
    posted_at: datetime | None = None
    discovered_at: datetime | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("salary_currency")
    @classmethod
    def currency_upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def salary_range_and_currency(self) -> JobCreate:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot exceed salary_max")
        if (
            self.salary_min is not None or self.salary_max is not None
        ) and not self.salary_currency:
            self.salary_currency = "USD"
        return self


class JobRead(BaseModel):
    id: UUID
    source: JobSource
    source_job_id: str
    company: str
    title: str
    description: str
    location: str | None
    remote_policy: RemotePolicy | None
    employment_type: EmploymentType | None
    seniority: Seniority | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    job_url: str | None
    application_url: str | None
    department: str | None
    posted_at: datetime | None
    discovered_at: datetime
    raw_data: dict[str, Any]
    content_hash: str
    is_duplicate_description: bool
    duplicate_description_job_ids: list[UUID]
    human_decision: HumanDecision | None = None
    human_decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    items: list[JobRead]
    total: int
    limit: int
    offset: int
