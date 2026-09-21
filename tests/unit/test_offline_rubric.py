"""Offline rubric is deterministic and never labeled as a live LLM."""

from app.agents.job_evaluation import JobEvaluationContext, build_evaluation_input
from app.models.enums import (
    EmploymentType,
    EvaluationMode,
    Recommendation,
    RemotePreference,
    Seniority,
)
from app.schemas.candidate import Compensation
from app.scoring.hard_filters import HardFilterCandidate, evaluate_hard_filters
from app.scoring.offline_rubric import OfflineRubricEvaluationRunner, evaluate_offline_rubric
from tests.support.evaluation import job_read, synthetic_evidence, synthetic_profile


def _candidate() -> HardFilterCandidate:
    return HardFilterCandidate(
        target_titles=["Senior Software Engineer", "Senior Backend Engineer", "Senior AI Engineer"],
        seniority=Seniority.SENIOR,
        preferred_locations=["Remote, US"],
        remote_preference=RemotePreference.REMOTE,
        employment_preferences=[EmploymentType.FULL_TIME, EmploymentType.CONTRACT],
        minimum_compensation=Compensation(amount=180000, currency="USD", period="year"),
    )


def test_offline_rubric_scores_without_llm() -> None:
    job = job_read()
    evidence = synthetic_evidence()
    hard_filter = evaluate_hard_filters(job, _candidate())
    result = evaluate_offline_rubric(job, evidence, hard_filter)
    assert result.recommendation in {Recommendation.APPLY, Recommendation.REVIEW}
    assert "language-model" in result.reasoning
    assert result.supporting_evidence_ids


def test_offline_runner_provenance_is_offline_rubric() -> None:
    job = job_read()
    evidence = synthetic_evidence()
    hard_filter = evaluate_hard_filters(job, _candidate())
    context = JobEvaluationContext(
        allowed_evidence_ids=frozenset(item.id for item in evidence),
        evidence=tuple(evidence),
        hard_filter=hard_filter,
    )
    prompt = build_evaluation_input(job, synthetic_profile(evidence), evidence, hard_filter)
    run = OfflineRubricEvaluationRunner().evaluate(prompt, context)
    assert run.provenance is not None
    assert run.provenance.evaluation_mode is EvaluationMode.OFFLINE_RUBRIC
    assert run.provenance.model is None
    assert run.provenance.provider == "offline_rubric"
    assert run.provenance.llm_request_id is None
    assert run.provenance.fallback_reason is None
    assert "language-model" in run.evaluation.reasoning
