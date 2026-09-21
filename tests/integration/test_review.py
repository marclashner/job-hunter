"""Review dashboard against live PostgreSQL."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_evaluation_runner
from app.db import Database
from app.main import app
from app.models.enums import Recommendation
from app.services.candidate import replace_from_seed
from app.services.candidate_seed import load_seed_bundle
from tests.support.evaluation import StubEvaluationRunner, evaluation
from tests.support.postgres import requires_postgres


@requires_postgres
def test_review_queue_filters_and_human_decision(database: Database) -> None:
    bundle = load_seed_bundle()
    session = database.session_factory()
    try:
        profile = replace_from_seed(session, bundle)
        session.commit()
        evidence_ids = [item.id for item in profile.evidence]
    finally:
        session.close()

    runner = StubEvaluationRunner(
        output=evaluation(
            supporting_evidence_ids=evidence_ids[:1],
            recommendation=Recommendation.APPLY,
            strengths=["Backend overlap."],
            concerns=["Salary unknown."],
            reasoning="Cited stored backend evidence for a healthcare API role.",
        )
    )
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            created = client.post(
                "/jobs",
                json={
                    "source": "manual",
                    "source_job_id": f"review-{uuid4()}",
                    "company": "Helix Care",
                    "title": "Senior Backend Engineer — Review UI",
                    "description": "Python APIs for healthcare workflow automation.",
                    "location": "Remote - United States",
                    "remote_policy": "remote",
                    "employment_type": "full_time",
                    "seniority": "senior",
                    "salary_min": 200000,
                    "salary_max": 240000,
                    "salary_currency": "USD",
                    "application_url": "https://example.com/apply/review-ui",
                },
            )
            assert created.status_code == 201, created.text
            job_id = created.json()["id"]
            evaluated = client.post(f"/jobs/{job_id}/evaluate?evaluation_mode=mock")
            assert evaluated.status_code == 201, evaluated.text

            summary = client.get("/review/summary")
            assert summary.status_code == 200, summary.text
            body = summary.json()
            assert body["evaluated"] >= 1
            assert body["applications_submitted"] == 0
            assert body["interviews"] == 0
            assert body["offers"] == 0

            queue = client.get(
                "/review/jobs",
                params={"recommendation": "apply", "minimum_score": 10},
            )
            assert queue.status_code == 200, queue.text
            items = queue.json()["items"]
            match = next(item for item in items if item["id"] == job_id)
            assert match["company"] == "Helix Care"
            assert match["recommendation"] == "apply"
            assert match["top_strengths"]
            assert "200,000" in match["compensation"]

            detail = client.get(f"/review/jobs/{job_id}")
            assert detail.status_code == 200, detail.text
            payload = detail.json()
            assert payload["application_url"] == "https://example.com/apply/review-ui"
            assert payload["evaluation"]["recommendation"] == "apply"
            assert payload["hard_filter"]["passed"] is True
            assert payload["supporting_evidence"]

            decided = client.post(
                f"/review/jobs/{job_id}/decision",
                json={"decision": "approve"},
            )
            assert decided.status_code == 200, decided.text
            assert decided.json()["human_decision"] == "approve"
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)
