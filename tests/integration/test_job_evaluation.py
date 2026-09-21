"""JobEvaluationAgent persistence against live PostgreSQL with a stub runner."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_evaluation_runner
from app.db import Database
from app.main import app
from app.models.enums import Recommendation
from app.repositories.evaluations import EvaluationRepository
from app.services.candidate import replace_from_seed
from app.services.candidate_seed import load_seed_bundle
from tests.support.evaluation import StubEvaluationRunner, evaluation
from tests.support.postgres import requires_postgres


@requires_postgres
def test_evaluate_endpoint_persists_grounded_result(database: Database) -> None:
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
            supporting_evidence_ids=evidence_ids[:2],
            recommendation=Recommendation.APPLY,
            reasoning="Cited stored evidence for backend healthcare overlap.",
            strengths=["Matches cited backend evidence."],
        )
    )

    def override_runner() -> StubEvaluationRunner:
        return runner

    suffix = uuid4()
    app.dependency_overrides[get_evaluation_runner] = override_runner
    try:
        with TestClient(app) as client:
            created = client.post(
                "/jobs",
                json={
                    "source": "manual",
                    "source_job_id": f"eval-{suffix}",
                    "company": "Helix Care",
                    "title": "Senior Backend Engineer — Healthcare AI",
                    "description": "Python APIs for healthcare workflow automation.",
                    "location": "Remote - United States",
                    "remote_policy": "remote",
                    "employment_type": "full_time",
                    "seniority": "senior",
                    "salary_min": 200000,
                    "salary_max": 240000,
                    "salary_currency": "USD",
                },
            )
            assert created.status_code == 201, created.text
            job_id = created.json()["id"]
            response = client.post(f"/jobs/{job_id}/evaluate")
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"] == job_id
    assert body["recommendation"] in {"apply", "review", "reject"}
    assert runner.last_input is not None
    assert "Senior Backend Engineer" in runner.last_input
    assert "hard_filter" in runner.last_input

    db_session = database.session_factory()
    try:
        stored = EvaluationRepository(db_session).latest_for_job(created.json()["id"])
        assert stored is not None
        assert stored.reasoning == body["reasoning"]
        assert stored.model
    finally:
        db_session.close()
