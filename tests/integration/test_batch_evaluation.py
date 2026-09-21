"""Batch evaluation pipeline against live PostgreSQL with a stub runner."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.agents.job_evaluation import (
    EvaluationAgentError,
    EvaluationRunResult,
    EvaluationUsage,
    JobEvaluationContext,
)
from app.api.deps import get_evaluation_runner
from app.db import Database
from app.main import app
from app.models.enums import Recommendation
from app.repositories.evaluations import EvaluationRepository
from app.schemas.evaluation import JobEvaluation
from app.services.candidate import replace_from_seed
from app.services.candidate_seed import load_seed_bundle
from app.services.rate_limit import RateLimiter
from tests.support.evaluation import StubEvaluationRunner, evaluation
from tests.support.postgres import requires_postgres


@pytest.fixture(autouse=True)
def disable_batch_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RateLimiter, "acquire", lambda self: None)


def _review_output() -> JobEvaluation:
    return evaluation(
        recommendation=Recommendation.REVIEW,
        supporting_evidence_ids=[],
        strengths=["Title overlaps stored backend work."],
        reasoning="Enough overlap to review without extra citations.",
        evidence_strength=1,
    )


def _apply_output() -> JobEvaluation:
    return evaluation(
        recommendation=Recommendation.APPLY,
        supporting_evidence_ids=[],
        strengths=["Title overlaps stored backend work."],
        reasoning="Strong overlap with stored backend work; review-grade citations omitted.",
        evidence_strength=2,
    )


def _seed_profile(database: Database) -> None:
    bundle = load_seed_bundle()
    session = database.session_factory()
    try:
        replace_from_seed(session, bundle)
        session.commit()
    finally:
        session.close()


def _job_scope(client: TestClient, job_ids: list[str]) -> dict[str, str]:
    stamps: list[datetime] = []
    for job_id in job_ids:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200, response.text
        raw = response.json()["discovered_at"]
        stamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    return {
        "discovered_after": min(stamps).isoformat(),
        "discovered_before": (max(stamps) + timedelta(seconds=1)).isoformat(),
    }


def _batch_payload(
    client: TestClient, job_ids: list[str], **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "source": "manual",
        "concurrency": 1,
        "limit": 20,
        **_job_scope(client, job_ids),
    }
    payload.update(overrides)
    return payload


def _create_job(client: TestClient, *, title: str, **fields: object) -> str:
    payload: dict[str, object] = {
        "source": "manual",
        "source_job_id": f"batch-{uuid4()}",
        "company": "Helix Care",
        "title": title,
        "description": "Python APIs for healthcare workflow automation.",
        "location": "Remote - United States",
        "remote_policy": "remote",
        "employment_type": "full_time",
        "seniority": "senior",
        "salary_min": 200000,
        "salary_max": 240000,
        "salary_currency": "USD",
    }
    payload.update(fields)
    created = client.post("/jobs", json=payload)
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


@requires_postgres
def test_batch_evaluates_unevaluated_jobs_and_skips_repeats(database: Database) -> None:
    _seed_profile(database)
    runner = StubEvaluationRunner(output=_review_output())
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            job_id = _create_job(client, title="Senior Backend Engineer — Healthcare AI")
            first = client.post("/evaluation/batch", json=_batch_payload(client, [job_id]))
            assert first.status_code == 200, first.text
            body = first.json()
            assert body["discovered"] == 1
            assert body["evaluated"] == 1
            assert body["review"] == 1
            assert body["errors"] == []
            assert runner.last_input is not None

            session = database.session_factory()
            try:
                stored = EvaluationRepository(session).latest_for_job(UUID(job_id))
                assert stored is not None
                first_id = stored.id
            finally:
                session.close()

            second = client.post("/evaluation/batch", json=_batch_payload(client, [job_id]))
            assert second.status_code == 200, second.text
            assert second.json()["discovered"] == 0
            session = database.session_factory()
            try:
                stored = EvaluationRepository(session).latest_for_job(UUID(job_id))
                assert stored is not None
                assert stored.id == first_id
            finally:
                session.close()

            third = client.post(
                "/evaluation/batch",
                json=_batch_payload(client, [job_id], reevaluate=True),
            )
            assert third.status_code == 200, third.text
            assert third.json()["discovered"] == 1
            assert third.json()["evaluated"] == 1
            session = database.session_factory()
            try:
                stored = EvaluationRepository(session).latest_for_job(UUID(job_id))
                assert stored is not None
                assert stored.id != first_id
            finally:
                session.close()
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_batch_hard_filters_before_agent_and_persists_reject(database: Database) -> None:
    _seed_profile(database)
    runner = StubEvaluationRunner(output=_review_output())
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            job_id = _create_job(
                client,
                title="Senior Backend Engineer — Onsite Desk",
                location="San Francisco, CA",
                remote_policy="onsite",
            )
            runner.last_input = None
            response = client.post("/evaluation/batch", json=_batch_payload(client, [job_id]))
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["discovered"] == 1
            assert body["hard_filtered"] == 1
            assert body["evaluated"] == 0
            assert runner.last_input is None
            session = database.session_factory()
            try:
                stored = EvaluationRepository(session).latest_for_job(UUID(job_id))
                assert stored is not None
                assert stored.recommendation == "reject"
                assert stored.model == "hard-filter"
            finally:
                session.close()
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_batch_continues_when_one_job_fails(database: Database) -> None:
    _seed_profile(database)
    fail_token = f"FAILAGENT-{uuid4().hex[:8]}"

    class PartialFailureRunner:
        calls = 0

        def evaluate(self, user_input: str, context: JobEvaluationContext) -> JobEvaluation:
            del context
            self.calls += 1
            if fail_token in user_input:
                raise EvaluationAgentError("forced failure")
            return _review_output()

    runner = PartialFailureRunner()
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            ok_id = _create_job(client, title="Senior Backend Engineer")
            bad_id = _create_job(client, title=f"Senior Backend Engineer {fail_token}")
            response = client.post(
                "/evaluation/batch",
                json=_batch_payload(client, [ok_id, bad_id]),
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["discovered"] == 2
            assert body["evaluated"] == 1
            assert len(body["errors"]) == 1
            assert body["errors"][0]["job_id"] == bad_id
            session = database.session_factory()
            try:
                assert EvaluationRepository(session).latest_for_job(UUID(ok_id)) is not None
                assert EvaluationRepository(session).latest_for_job(UUID(bad_id)) is None
            finally:
                session.close()
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_batch_dry_run_does_not_call_agent_or_persist(database: Database) -> None:
    _seed_profile(database)
    runner = StubEvaluationRunner(output=_review_output())
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            job_id = _create_job(client, title="Senior Backend Engineer — Dry Run")
            runner.last_input = None
            response = client.post(
                "/evaluation/batch",
                json=_batch_payload(client, [job_id], dry_run=True),
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["dry_run"] is True
            assert body["discovered"] == 1
            assert body["evaluated"] == 1
            assert body["apply"] == 0
            assert body["review"] == 0
            assert body["reject"] == 0
            assert runner.last_input is None
            session = database.session_factory()
            try:
                assert EvaluationRepository(session).latest_for_job(UUID(job_id)) is None
            finally:
                session.close()
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_batch_respects_limit_and_records_usage(database: Database) -> None:
    _seed_profile(database)

    class UsageRunner:
        def evaluate(self, user_input: str, context: JobEvaluationContext) -> EvaluationRunResult:
            del user_input, context
            return EvaluationRunResult(
                evaluation=_apply_output(),
                usage=EvaluationUsage(
                    input_tokens=100,
                    output_tokens=20,
                    total_tokens=120,
                    requests=1,
                    estimated_cost_usd=0.000027,
                    raw={"input_tokens": 100, "output_tokens": 20},
                ),
            )

    runner = UsageRunner()
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            job_a = _create_job(client, title="Senior Backend Engineer A")
            job_b = _create_job(client, title="Senior Backend Engineer B")
            response = client.post(
                "/evaluation/batch",
                json=_batch_payload(client, [job_a, job_b], concurrency=2, limit=1),
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["discovered"] == 1
            assert body["evaluated"] == 1
            assert body["usage"]["input_tokens"] == 100
            assert body["usage"]["output_tokens"] == 20
            assert body["usage"]["estimated_cost_usd"] == 0.000027
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)


@requires_postgres
def test_batch_date_range_filters_discovered_jobs(database: Database) -> None:
    _seed_profile(database)
    runner = StubEvaluationRunner(output=_review_output())
    app.dependency_overrides[get_evaluation_runner] = lambda: runner
    try:
        with TestClient(app) as client:
            _create_job(client, title="Senior Backend Engineer — Range")
            response = client.post(
                "/evaluation/batch",
                json={
                    "source": "manual",
                    "concurrency": 1,
                    "discovered_after": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                },
            )
            assert response.status_code == 200, response.text
            assert response.json()["discovered"] == 0
    finally:
        app.dependency_overrides.pop(get_evaluation_runner, None)
