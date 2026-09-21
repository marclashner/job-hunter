"""Listing enrichment: regex salary + geo, optional LLM stub."""

from app.models.enums import JobSource, RemotePolicy, SalarySource
from app.schemas.job import JobCreate
from app.services.listing_enrichment import enrich_job_create
from app.sources.compensation import ParsedCompensation


class _StubExtractor:
    def extract(self, *, title: str, location: str | None, description: str) -> ParsedCompensation:
        del title, location, description
        return ParsedCompensation(
            salary_min=170000,
            salary_max=200000,
            salary_currency="USD",
            quote="stubbed",
        )


def _job(**overrides: object) -> JobCreate:
    values: dict[str, object] = {
        "source": JobSource.MANUAL,
        "source_job_id": "enrich-1",
        "company": "Helix Care",
        "title": "Senior Backend Engineer",
        "description": "Build APIs.",
        "location": "Remote - United States",
        "remote_policy": RemotePolicy.REMOTE,
    }
    values.update(overrides)
    return JobCreate.model_validate(values)


def test_regex_salary_and_us_geo() -> None:
    job = enrich_job_create(
        _job(description="The base pay for this role is: $198,720 - $260,820 per year.")
    )
    assert job.salary_min == 198720
    assert job.salary_max == 260820
    assert job.salary_source is SalarySource.REGEX
    assert job.eligible_countries == ["US"]


def test_structured_salary_is_not_overwritten() -> None:
    job = enrich_job_create(_job(salary_min=200000, salary_max=240000, salary_currency="USD"))
    assert job.salary_min == 200000
    assert job.salary_source is SalarySource.STRUCTURED_API


def test_llm_used_when_pay_mentioned_without_numbers() -> None:
    job = enrich_job_create(
        _job(description="Competitive salary with generous annual cash bonus"),
        extractor=_StubExtractor(),
    )
    assert job.salary_min == 170000
    assert job.salary_source is SalarySource.LLM
