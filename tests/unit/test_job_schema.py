"""Job schema validation tests."""

import pytest
from pydantic import ValidationError

from app.models.enums import JobSource
from app.schemas.job import JobCreate


def test_salary_min_cannot_exceed_max() -> None:
    with pytest.raises(ValidationError):
        JobCreate(
            source=JobSource.MANUAL,
            source_job_id="x",
            company="Acme",
            title="Engineer",
            description="Build things",
            salary_min=200000,
            salary_max=150000,
        )


def test_salary_defaults_currency_to_usd() -> None:
    payload = JobCreate(
        source=JobSource.MANUAL,
        source_job_id="x",
        company="Acme",
        title="Engineer",
        description="Build things",
        salary_min=180000,
    )
    assert payload.salary_currency == "USD"
