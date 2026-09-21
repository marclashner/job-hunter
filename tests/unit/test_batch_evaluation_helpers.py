"""Batch evaluation request validation and helpers (no database)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agents.job_evaluation import EvaluationRunResult, EvaluationUsage
from app.models.enums import EvaluationMode, Recommendation
from app.schemas.evaluation import BatchEvaluationRequest, JobEvaluation
from app.scoring.hard_filters import HardFilterResult
from app.services.evaluation import evaluation_from_hard_filter_failure, unwrap_evaluation_run
from tests.support.evaluation import StubEvaluationRunner, evaluation


def test_batch_request_rejects_inverted_date_range() -> None:
    with pytest.raises(ValidationError):
        BatchEvaluationRequest(
            discovered_after=datetime(2026, 9, 21, tzinfo=UTC),
            discovered_before=datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_unwrap_evaluation_run_accepts_plain_evaluation() -> None:
    model = evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[])
    runner = StubEvaluationRunner(output=model)
    raw, usage, provenance = unwrap_evaluation_run(model, runner=runner)
    assert raw is model
    assert usage is None
    assert provenance.evaluation_mode is EvaluationMode.MOCK


def test_unwrap_evaluation_run_reads_usage() -> None:
    model = evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[])
    usage = EvaluationUsage(input_tokens=10, output_tokens=4, total_tokens=14, requests=1)
    runner = StubEvaluationRunner(output=model)
    raw, extracted, provenance = unwrap_evaluation_run(
        EvaluationRunResult(evaluation=model, usage=usage, provenance=None),
        runner=runner,
    )
    assert raw is model
    assert extracted is not None
    assert extracted.input_tokens == 10
    assert provenance.evaluation_mode is EvaluationMode.MOCK


def test_hard_filter_failure_evaluation_is_reject() -> None:
    hard_filter = HardFilterResult(
        passed=False,
        failed_rules=["excluded_industry"],
        warnings=[],
        missing_information=[],
        salary_unknown=False,
    )
    result = evaluation_from_hard_filter_failure(hard_filter)
    assert result.recommendation is Recommendation.REJECT
    assert result.overall_score == 0
    assert "excluded_industry" in result.reasoning


def test_job_evaluation_type_still_validates() -> None:
    assert isinstance(
        evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[]),
        JobEvaluation,
    )
