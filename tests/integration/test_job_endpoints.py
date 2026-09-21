"""Live job ingestion HTTP tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from tests.support.postgres import requires_postgres


def _payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "source": "manual",
        "source_job_id": f"job-{uuid4()}",
        "company": "Northwind Health",
        "title": "Senior Backend Engineer",
        "description": "Own Python services, PostgreSQL, and on-call for clinical operations APIs.",
        "location": "Remote - US",
        "remote_policy": "remote",
        "employment_type": "full_time",
        "seniority": "senior",
        "salary_min": 180000,
        "salary_max": 220000,
        "salary_currency": "USD",
        "job_url": "https://example.com/jobs/backend",
        "application_url": "https://example.com/jobs/backend/apply",
        "department": "Platform",
        "raw_data": {"board": "manual-fixture", "external_id": "abc"},
    }
    values.update(overrides)
    return values


@requires_postgres
def test_job_crud_filters_pagination_and_duplicates() -> None:
    suffix = uuid4()
    description = f"Unique listing body for duplicate detection {suffix}"
    first = _payload(
        source_job_id=f"src-a-{suffix}",
        title=f"Senior Backend Engineer {suffix}",
        description=description,
        location="San Francisco, CA",
        salary_min=190000,
        salary_max=230000,
    )
    second = _payload(
        source_job_id=f"src-b-{suffix}",
        title=f"Staff Platform Engineer {suffix}",
        description=description,
        location="New York, NY",
        remote_policy="hybrid",
        seniority="staff",
        salary_min=210000,
        salary_max=260000,
    )
    junior = _payload(
        source_job_id=f"src-c-{suffix}",
        title=f"Junior Support Engineer {suffix}",
        description=f"Different description {suffix}",
        location="Austin, TX",
        remote_policy="onsite",
        seniority="junior",
        salary_min=90000,
        salary_max=110000,
    )

    with TestClient(app) as client:
        created_first = client.post("/jobs", json=first)
        created_second = client.post("/jobs", json=second)
        created_junior = client.post("/jobs", json=junior)
        conflict = client.post("/jobs", json=first)

        assert created_first.status_code == 201
        assert created_second.status_code == 201
        assert created_junior.status_code == 201
        assert conflict.status_code == 409

        first_id = created_first.json()["id"]
        second_body = created_second.json()
        first_body = client.get(f"/jobs/{first_id}").json()
        assert first_body["raw_data"] == first["raw_data"]
        assert first_body["content_hash"] == second_body["content_hash"]
        assert first_body["is_duplicate_description"] is True
        assert second_body["id"] in first_body["duplicate_description_job_ids"]
        assert second_body["is_duplicate_description"] is True

        fetched = client.get(f"/jobs/{first_id}")
        assert fetched.status_code == 200
        assert fetched.json()["source_job_id"] == first["source_job_id"]

        missing = client.get("/jobs/00000000-0000-0000-0000-000000000001")
        assert missing.status_code == 404

        listed = client.get("/jobs", params={"title": "Backend", "limit": 50})
        assert listed.status_code == 200
        titles = {item["title"] for item in listed.json()["items"]}
        assert first["title"] in titles

        by_source = client.get("/jobs", params={"source": "manual", "limit": 100})
        assert by_source.status_code == 200
        assert by_source.json()["total"] >= 3

        by_location = client.get("/jobs", params={"location": "Francisco"})
        assert any(item["id"] == first_id for item in by_location.json()["items"])

        by_remote = client.get("/jobs", params={"remote_policy": "hybrid"})
        assert any(item["id"] == second_body["id"] for item in by_remote.json()["items"])

        by_seniority = client.get("/jobs", params={"seniority": "junior"})
        assert any(
            item["id"] == created_junior.json()["id"] for item in by_seniority.json()["items"]
        )

        by_salary = client.get("/jobs", params={"minimum_salary": 200000})
        salary_ids = {item["id"] for item in by_salary.json()["items"]}
        assert second_body["id"] in salary_ids
        assert created_junior.json()["id"] not in salary_ids

        page = client.get("/jobs", params={"title": str(suffix), "limit": 1, "offset": 0})
        next_page = client.get("/jobs", params={"title": str(suffix), "limit": 1, "offset": 1})
        assert page.json()["limit"] == 1
        assert page.json()["total"] == 3
        assert page.json()["items"][0]["id"] != next_page.json()["items"][0]["id"]
