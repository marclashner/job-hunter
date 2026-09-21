"""Hard-filter endpoint against live PostgreSQL."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.db import Database
from app.main import app
from app.services.candidate import replace_from_seed
from app.services.candidate_seed import load_seed_bundle
from tests.support.postgres import requires_postgres


@requires_postgres
def test_hard_filter_endpoint_pass_and_fail(database: Database) -> None:
    bundle = load_seed_bundle()
    session = database.session_factory()
    try:
        replace_from_seed(session, bundle)
        session.commit()
    finally:
        session.close()

    suffix = uuid4()
    with TestClient(app) as client:
        matching = client.post(
            "/jobs",
            json={
                "source": "manual",
                "source_job_id": f"hf-pass-{suffix}",
                "company": "Helix Care",
                "title": "Senior Backend Engineer",
                "description": "Python and PostgreSQL for healthcare workflow automation.",
                "location": "Remote - United States",
                "remote_policy": "remote",
                "employment_type": "full_time",
                "seniority": "senior",
                "salary_min": 200000,
                "salary_max": 240000,
                "salary_currency": "USD",
            },
        )
        mismatch = client.post(
            "/jobs",
            json={
                "source": "manual",
                "source_job_id": f"hf-fail-{suffix}",
                "company": "Onsite Labs",
                "title": "Engineering Manager",
                "description": "People management in our San Francisco office.",
                "location": "San Francisco, CA",
                "remote_policy": "onsite",
                "employment_type": "full_time",
                "seniority": "senior",
                "salary_min": 200000,
                "salary_max": 240000,
                "salary_currency": "USD",
            },
        )
        unknown_salary = client.post(
            "/jobs",
            json={
                "source": "manual",
                "source_job_id": f"hf-salary-{suffix}",
                "company": "Helix Care",
                "title": "Senior Backend Engineer",
                "description": "Python APIs for healthcare operations.",
                "location": "Remote - United States",
                "remote_policy": "remote",
                "employment_type": "full_time",
                "seniority": "senior",
            },
        )

        assert matching.status_code == 201, matching.text
        assert mismatch.status_code == 201, mismatch.text
        assert unknown_salary.status_code == 201, unknown_salary.text

        passed = client.post(f"/jobs/{matching.json()['id']}/hard-filter")
        failed = client.post(f"/jobs/{mismatch.json()['id']}/hard-filter")
        salary = client.post(f"/jobs/{unknown_salary.json()['id']}/hard-filter")

    assert passed.status_code == 200, passed.text
    assert passed.json()["passed"] is True
    assert passed.json()["failed_rules"] == []
    assert passed.json()["salary_unknown"] is False

    assert failed.status_code == 200, failed.text
    assert failed.json()["passed"] is False
    assert "unacceptable_onsite_requirement" in failed.json()["failed_rules"]
    assert "target_role_mismatch" in failed.json()["failed_rules"]

    assert salary.status_code == 200, salary.text
    assert salary.json()["passed"] is True
    assert salary.json()["salary_unknown"] is True
    assert "job_salary" in salary.json()["missing_information"]
