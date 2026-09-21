"""Run JobEvaluationAgent, ground the result, and persist it."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.agents.grounding import ground_evaluation
from app.agents.job_evaluation import (
    JobEvaluationContext,
    JobEvaluationRunner,
    OpenAIAgentsEvaluationRunner,
    build_evaluation_input,
)
from app.config import get_settings
from app.models.enums import Recommendation
from app.models.evaluation import JobEvaluationRecord
from app.repositories.evaluations import EvaluationRepository
from app.repositories.jobs import JobRepository
from app.schemas.evaluation import JobEvaluation, JobEvaluationRead
from app.scoring.hard_filters import HardFilterResult, evaluate_hard_filters
from app.services.candidate import (
    PRIMARY_PROFILE_KEY,
    evidence_to_read,
    profile_to_read,
    require_profile,
)
from app.services.jobs import JobNotFoundError, get_job


def evaluate_job(
    session: Session,
    job_id: uuid.UUID,
    *,
    runner: JobEvaluationRunner | None = None,
    profile_key: str = PRIMARY_PROFILE_KEY,
) -> JobEvaluationRead:
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
    active_runner = runner or OpenAIAgentsEvaluationRunner()
    raw = active_runner.evaluate(user_input, context)
    grounded = ground_evaluation(
        raw,
        allowed_evidence_ids=set(context.allowed_evidence_ids),
        evidence=evidence,
        hard_filter=hard_filter,
    )
    record = _to_record(grounded, job_id=job.id, profile_id=profile.id, hard_filter=hard_filter)
    EvaluationRepository(session).add(record)
    session.commit()
    session.refresh(record)
    return _to_read(record, grounded, hard_filter)


def _to_record(
    evaluation: JobEvaluation,
    *,
    job_id: uuid.UUID,
    profile_id: uuid.UUID,
    hard_filter: HardFilterResult,
) -> JobEvaluationRecord:
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
        model=get_settings().openai_model,
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
