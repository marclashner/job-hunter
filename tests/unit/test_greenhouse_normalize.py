"""Greenhouse normalization and HTML-to-text tests."""

import pytest

from app.models.enums import EmploymentType, JobSource, RemotePolicy, Seniority
from app.sources.base import JobNormalizationError, RawJob
from app.sources.greenhouse import GreenhouseClient
from app.sources.html_text import html_to_text
from tests.support.greenhouse import BOARD_TOKEN, greenhouse_job


def test_html_to_text_strips_tags_not_scraping() -> None:
    text = html_to_text("<div><h1>Engineer</h1><p>Build&nbsp;APIs.</p><script>x()</script></div>")
    assert "Engineer" in text
    assert "Build" in text
    assert "x()" not in text
    assert "<p>" not in text
    leftover = html_to_text("Pay Transparency: </strong>The base pay for this role is: $198,720")
    assert "<" not in leftover
    assert "$198,720" in leftover


def test_normalize_maps_greenhouse_json_to_job_create() -> None:
    client = GreenhouseClient(sleep=lambda _delay: None)
    raw = RawJob(
        source=JobSource.GREENHOUSE,
        company_identifier=BOARD_TOKEN,
        company_name="Acme Co",
        payload=greenhouse_job(42),
    )
    job = client.normalize(raw)
    assert job.source is JobSource.GREENHOUSE
    assert job.source_job_id == "42"
    assert job.company == "Acme Co"
    assert job.title == "Senior Backend Engineer"
    assert "Build Python APIs" in job.description
    assert "<p>" not in job.description
    assert job.location == "Remote - United States"
    assert job.remote_policy is RemotePolicy.REMOTE
    assert job.seniority is Seniority.SENIOR
    assert job.employment_type is EmploymentType.FULL_TIME
    assert job.department == "Engineering"
    assert job.job_url and job.job_url.endswith("/jobs/42")
    assert job.raw_data["board_token"] == BOARD_TOKEN
    assert job.raw_data["payload"]["id"] == 42
    client.close()


def test_normalize_rejects_missing_description() -> None:
    client = GreenhouseClient(sleep=lambda _delay: None)
    raw = RawJob(
        source=JobSource.GREENHOUSE,
        company_identifier=BOARD_TOKEN,
        company_name="Acme Co",
        payload={"id": 7, "title": "Engineer", "content": "<p>   </p>"},
    )
    with pytest.raises(JobNormalizationError):
        client.normalize(raw)
    client.close()
