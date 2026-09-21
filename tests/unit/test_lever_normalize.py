"""Lever normalization tests."""

import pytest

from app.models.enums import EmploymentType, JobSource, RemotePolicy, Seniority
from app.sources.base import JobNormalizationError, RawJob
from app.sources.lever import LeverClient
from tests.support.lever import SITE, lever_posting


def test_normalize_maps_lever_json_to_job_create() -> None:
    client = LeverClient(sleep=lambda _delay: None)
    raw = RawJob(
        source=JobSource.LEVER,
        company_identifier=SITE,
        company_name=SITE,
        payload=lever_posting("abc-123"),
    )
    job = client.normalize(raw)
    client.close()
    assert job.source is JobSource.LEVER
    assert job.source_job_id == "abc-123"
    assert job.company == SITE
    assert job.title == "Senior Backend Engineer"
    assert "Build Python APIs" in job.description
    assert "Python" in job.description
    assert "<p>" not in job.description
    assert job.location == "Remote - United States"
    assert job.remote_policy is RemotePolicy.REMOTE
    assert job.seniority is Seniority.SENIOR
    assert job.employment_type is EmploymentType.FULL_TIME
    assert job.department == "Engineering"
    assert job.job_url and job.job_url.endswith("/abc-123")
    assert job.application_url and job.application_url.endswith("/apply")
    assert job.posted_at is not None
    assert job.raw_data["site"] == SITE
    assert job.raw_data["payload"]["id"] == "abc-123"


def test_normalize_rejects_missing_description() -> None:
    client = LeverClient(sleep=lambda _delay: None)
    raw = RawJob(
        source=JobSource.LEVER,
        company_identifier=SITE,
        company_name=SITE,
        payload={"id": "empty", "text": "Engineer", "description": "<p>  </p>"},
    )
    with pytest.raises(JobNormalizationError):
        client.normalize(raw)
    client.close()
