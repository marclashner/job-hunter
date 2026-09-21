"""Run JobEvaluationAgent, ground the result, and persist it."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agents.grounding import ground_evaluation
from app.agents.job_evaluation import (
    EvaluationRunResult,
    EvaluationUsage,
    JobEvaluationContext,
    JobEvaluationRunner,
    OpenAIAgentsEvaluationRunner,
    build_evaluation_input,
)
from app.config import get_settings
from app.models.candidate import CandidateProfile
from app.models.enums import Recommendation
from app.models.evaluation import JobEvaluationRecord
from app.models.job import Job
from app.repositories.evaluations import EvaluationRepository
from app.repositories.jobs import JobRepository
from app.schemas.candidate import CandidateEvidenceRead, CandidateProfileRead
from app.schemas.evaluation import JobEvaluation, JobEvaluationRead
from app.schemas.job import JobRead
from app.scoring.hard_filters import HardFilterResult, evaluate_hard_filters
from app.services.candidate import (
    PRIMARY_PROFILE_KEY,
    evidence_to_read,
    profile_to_read,
    require_profile,
)
from app.services.jobs import JobNotFoundError, get_job

HARD_FILTER_MODEL = "hard-filter"


@dataclass(frozen=True)
class EvaluationInputs:
    job_row: Job
    job: JobRead
    profile: CandidateProfile
    profile_read: CandidateProfileRead
    evidence: list[CandidateEvidenceRead]
    hard_filter: HardFilterResult
    context: JobEvaluationContext
    user_input: str


def load_evaluation_inputs(
    session: Session,
    job_id: uuid.UUID,
    *,
    profile_key: str = PRIMARY_PROFILE_KEY,
) -> EvaluationInputs:
    job_row = JobRepository(session).get_by_id(job_id)
    if job_row is None:
        raise JobNotFoundError(str(job_id))
    profile = require_profile(session, profile_key)
    job = get_job(session, job_id)
    profile_read = profile_to_read(profile)
    evidence = [evidence_to_read(item) for item in profile.evidence]
    hard_filter = evaluate_hard_filters(job_row, profile)
    context = JobEvaluationContext(
        allowed_evidence_ids=frozenset(item.id for item in evidence),
        evidence=tuple(evidence),
        hard_filter=hard_filter,
    )
    user_input = build_evaluation_input(job, profile_read, evidence, hard_filter)
    return EvaluationInputs(
        job_row=job_row,
        job=job,
        profile=profile,
        profile_read=profile_read,
        evidence=evidence,
        hard_filter=hard_filter,
        context=context,
        user_input=user_input,
    )


def unwrap_evaluation_run(
    result: JobEvaluation | EvaluationRunResult,
) -> tuple[JobEvaluation, EvaluationUsage | None]:
    if isinstance(result, EvaluationRunResult):
        return result.evaluation, result.usage
    return result, None


def evaluation_from_hard_filter_failure(hard_filter: HardFilterResult) -> JobEvaluation:
    rules = ", ".join(str(rule) for rule in hard_filter.failed_rules) or "unknown"
    return JobEvaluation.model_validate(
        {
            "overall_score": 0,
            "technical_fit": 0,
            "domain_fit": 0,
            "product_fit": 0,
            "ai_relevance": 0,
            "seniority_fit": 0,
            "company_interest_fit": 0,
            "evidence_strength": 0,
            "recommendation": Recommendation.REJECT,
            "strengths": [],
            "concerns": [f"Failed hard filter: {rules}"],
            "missing_information": list(hard_filter.missing_information),
            "supporting_evidence_ids": [],
            "reasoning": (
                "Discarded before JobEvaluationAgent because deterministic hard filters failed: "
                f"{rules}."
            ),
        }
    )


def persist_evaluation(
    session: Session,
    evaluation: JobEvaluation,
    *,
    job_id: uuid.UUID,
    profile_id: uuid.UUID,
    hard_filter: HardFilterResult,
    model: str,
    usage: EvaluationUsage | None = None,
) -> JobEvaluationRead:
    record = _to_record(
        evaluation,
        job_id=job_id,
        profile_id=profile_id,
        hard_filter=hard_filter,
        model=model,
        usage=usage,
    )
    EvaluationRepository(session).add(record)
    session.commit()
    session.refresh(record)
    return _to_read(record, evaluation, hard_filter)


def evaluate_job(
    session: Session,
    job_id: uuid.UUID,
    *,
    runner: JobEvaluationRunner | None = None,
    profile_key: str = PRIMARY_PROFILE_KEY,
) -> JobEvaluationRead:
    inputs = load_evaluation_inputs(session, job_id, profile_key=profile_key)
    active_runner = runner or OpenAIAgentsEvaluationRunner()
    raw, usage = unwrap_evaluation_run(active_runner.evaluate(inputs.user_input, inputs.context))
    grounded = ground_evaluation(
        raw,
        allowed_evidence_ids=set(inputs.context.allowed_evidence_ids),
        evidence=inputs.evidence,
        hard_filter=inputs.hard_filter,
    )
    return persist_evaluation(
        session,
        grounded,
        job_id=inputs.job.id,
        profile_id=inputs.profile.id,
        hard_filter=inputs.hard_filter,
        model=get_settings().openai_model,
        usage=usage,
    )


def _to_record(
    evaluation: JobEvaluation,
    *,
    job_id: uuid.UUID,
    profile_id: uuid.UUID,
    hard_filter: HardFilterResult,
    model: str,
    usage: EvaluationUsage | None = None,
) -> JobEvaluationRecord:
    cost = None
    if usage is not None and usage.estimated_cost_usd is not None:
        cost = Decimal(str(usage.estimated_cost_usd))
    return JobEvaluationRecord(
        id=uuid.uuid4(),
        job_id=job_id,
        profile_id=profile_id,
        overall_score=evaluation.overall_score,
        technical_fit=evaluation.technical_fit,
        domain_fit=evaluation.domain_fit,
        product_fit=evaluation.product_fit,
        ai_relevance=evaluation.ai_relevance,
        seniority_fit=evaluation.seniority_fit,
        company_interest_fit=evaluation.company_interest_fit,
        evidence_strength=evaluation.evidence_strength,
        recommendation=evaluation.recommendation.value,
        strengths=list(evaluation.strengths),
        concerns=list(evaluation.concerns),
        missing_information=list(evaluation.missing_information),
        supporting_evidence_ids=[str(item) for item in evaluation.supporting_evidence_ids],
        reasoning=evaluation.reasoning,
        hard_filter=hard_filter.model_dump(mode="json"),
        model=model,
        usage_input_tokens=None if usage is None else usage.input_tokens,
        usage_output_tokens=None if usage is None else usage.output_tokens,
        usage_total_tokens=None if usage is None else usage.total_tokens,
        usage_requests=None if usage is None else usage.requests,
        estimated_cost_usd=cost,
        usage_metadata={} if usage is None else dict(usage.raw),
    )


def _to_read(
    record: JobEvaluationRecord,
    evaluation: JobEvaluation,
    hard_filter: HardFilterResult,
) -> JobEvaluationRead:
    return JobEvaluationRead(
        id=record.id,
        job_id=record.job_id,
        profile_id=record.profile_id,
        model=record.model,
        hard_filter=hard_filter,
        created_at=record.created_at,
        updated_at=record.updated_at,
        overall_score=evaluation.overall_score,
        technical_fit=evaluation.technical_fit,
        domain_fit=evaluation.domain_fit,
        product_fit=evaluation.product_fit,
        ai_relevance=evaluation.ai_relevance,
        seniority_fit=evaluation.seniority_fit,
        company_interest_fit=evaluation.company_interest_fit,
        evidence_strength=evaluation.evidence_strength,
        recommendation=Recommendation(record.recommendation),
        strengths=evaluation.strengths,
        concerns=evaluation.concerns,
        missing_information=evaluation.missing_information,
        supporting_evidence_ids=evaluation.supporting_evidence_ids,
        reasoning=evaluation.reasoning,
    )
