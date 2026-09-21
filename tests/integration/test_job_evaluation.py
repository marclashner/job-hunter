"""JobEvaluationAgent persistence against live PostgreSQL with a stub runner."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.agents.job_evaluation import EvaluationAgentError, JobEvaluationContext
from app.api.deps import get_evaluation_runner
from app.db import Database
from app.main import app
from app.models.enums import EvaluationMode, Recommendation
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
            response = client.post(f"/jobs/{job_id}/evaluate?evaluation_mode=mock")
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["job_id"] == job_id
    assert body["recommendation"] in {"apply", "review", "reject"}
    assert body["evaluation_mode"] == "mock"
    assert body["model"] is None
    assert body["provider"] == "stub"
    assert body["llm_request_id"] is None
    assert body["fallback_reason"] is None
    assert runner.last_input is not None
    assert "Senior Backend Engineer" in runner.last_input
    assert "hard_filter" in runner.last_input

    db_session = database.session_factory()
    try:
        stored = EvaluationRepository(db_session).latest_for_job(created.json()["id"])
        assert stored is not None
        assert stored.reasoning == body["reasoning"]
        assert stored.evaluation_mode == "mock"
        assert stored.model is None
        assert stored.provider == "stub"
    finally:
        db_session.close()


def _seed_and_job(database: Database, client: TestClient) -> str:
    bundle = load_seed_bundle()
    session = database.session_factory()
    try:
        replace_from_seed(session, bundle)
        session.commit()
    finally:
        session.close()
    created = client.post(
        "/jobs",
        json={
            "source": "manual",
            "source_job_id": f"eval-{uuid4()}",
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
    return str(created.json()["id"])


@requires_postgres
def test_live_llm_mode_rejects_mock_runner(database: Database) -> None:
    runner = StubEvaluationRunner(
        output=evaluation(
            recommendation=Recommendation.REVIEW,
            supporting_evidence_ids=[],
            strengths=["Title overlaps stored backend work."],
            reasoning="Should never be persisted as live_llm.",
        )
    )
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            job_id = _seed_and_job(database, client)
            response = client.post(f"/jobs/{job_id}/evaluate")
            assert response.status_code == 409, response.text
            assert "live_llm" in response.json()["detail"]
            session = database.session_factory()
            try:
                assert EvaluationRepository(session).latest_for_job(UUID(job_id)) is None
            finally:
                session.close()
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_live_llm_failure_returns_error_and_does_not_persist(database: Database) -> None:
    class FailingLiveRunner:
        evaluation_mode = EvaluationMode.LIVE_LLM

        def evaluate(self, user_input: str, context: JobEvaluationContext) -> None:
            del user_input, context
            raise EvaluationAgentError("JobEvaluationAgent run failed")

    app.dependency_overrides[get_evaluation_runner] = lambda: FailingLiveRunner()
    try:
        with TestClient(app) as client:
            job_id = _seed_and_job(database, client)
            response = client.post(f"/jobs/{job_id}/evaluate?evaluation_mode=live_llm")
            assert response.status_code == 502, response.text
            session = database.session_factory()
            try:
                assert EvaluationRepository(session).latest_for_job(UUID(job_id)) is None
            finally:
                session.close()
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_offline_rubric_mode_persists_offline_provenance(database: Database) -> None:
    with TestClient(app) as client:
        job_id = _seed_and_job(database, client)
        response = client.post(f"/jobs/{job_id}/evaluate?evaluation_mode=offline_rubric")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["evaluation_mode"] == "offline_rubric"
    assert body["model"] is None
    assert body["provider"] == "offline_rubric"
    assert body["llm_request_id"] is None
    assert body["fallback_reason"] is None
    assert "language-model" in body["reasoning"]
    session = database.session_factory()
    try:
        stored = EvaluationRepository(session).latest_for_job(UUID(job_id))
        assert stored is not None
        assert stored.evaluation_mode == "offline_rubric"
        assert stored.provider == "offline_rubric"
    finally:
        session.close()
