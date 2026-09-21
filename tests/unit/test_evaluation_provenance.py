"""Evaluation mode selection: live, offline, and mock must stay distinct."""

import pytest

from app.agents.job_evaluation import (
    EvaluationModeConflictError,
    EvaluationProvenance,
    EvaluationRunResult,
    OpenAIAgentsEvaluationRunner,
)
from app.models.enums import EvaluationMode, Recommendation
from app.scoring.offline_rubric import OfflineRubricEvaluationRunner
from app.services.evaluation import resolve_evaluation_runner, unwrap_evaluation_run
from tests.support.evaluation import StubEvaluationRunner, evaluation


def test_live_mode_rejects_mock_runner() -> None:
    runner = StubEvaluationRunner(
        output=evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[])
    )
    with pytest.raises(EvaluationModeConflictError, match="live_llm"):
        resolve_evaluation_runner(EvaluationMode.LIVE_LLM, runner)


def test_live_mode_uses_openai_runner_when_none_injected() -> None:
    runner = resolve_evaluation_runner(EvaluationMode.LIVE_LLM, None)
    assert isinstance(runner, OpenAIAgentsEvaluationRunner)
    assert runner.evaluation_mode is EvaluationMode.LIVE_LLM


def test_offline_mode_uses_offline_runner_even_if_stub_injected() -> None:
    stub = StubEvaluationRunner(
        output=evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[])
    )
    runner = resolve_evaluation_runner(EvaluationMode.OFFLINE_RUBRIC, stub)
    assert isinstance(runner, OfflineRubricEvaluationRunner)


def test_mock_mode_requires_mock_runner() -> None:
    with pytest.raises(EvaluationModeConflictError, match="injected mock"):
        resolve_evaluation_runner(EvaluationMode.MOCK, None)


def test_unlabeled_result_cannot_be_treated_as_live_llm() -> None:
    live = OpenAIAgentsEvaluationRunner()
    result = evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[])
    with pytest.raises(EvaluationModeConflictError, match="unlabeled"):
        unwrap_evaluation_run(result, runner=live)


def test_live_result_cannot_carry_fallback_reason() -> None:
    live = OpenAIAgentsEvaluationRunner()
    scored = evaluation(recommendation=Recommendation.REVIEW, supporting_evidence_ids=[])
    with pytest.raises(EvaluationModeConflictError, match="fallback_reason"):
        unwrap_evaluation_run(
            EvaluationRunResult(
                evaluation=scored,
                provenance=EvaluationProvenance(
                    evaluation_mode=EvaluationMode.LIVE_LLM,
                    model="gpt-4o-mini",
                    provider="openai",
                    fallback_reason="offline_rubric",
                ),
            ),
            runner=live,
        )
