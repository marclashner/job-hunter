"""In-process batch evaluation: hard filters, then JobEvaluationAgent, no queue."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agents.grounding import EvaluationGroundingError, ground_evaluation
from app.agents.job_evaluation import (
    EvaluationAgentError,
    EvaluationUsage,
    JobEvaluationRunner,
)
from app.config import get_settings
from app.logging_events import log_event, log_exception
from app.models.enums import Recommendation
from app.repositories.jobs import JobRepository
from app.schemas.evaluation import (
    BatchEvaluationError,
    BatchEvaluationRequest,
    BatchEvaluationResult,
    ModelUsageSummary,
)
from app.services.evaluation import (
    HARD_FILTER_MODEL,
    evaluation_from_hard_filter_failure,
    load_evaluation_inputs,
    persist_evaluation,
    unwrap_evaluation_run,
)
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class _JobOutcome:
    hard_filtered: bool = False
    evaluated: bool = False
    recommendation: Recommendation | None = None
    usage: EvaluationUsage | None = None
    error: BatchEvaluationError | None = None


def run_batch_evaluation(
    session: Session,
    payload: BatchEvaluationRequest,
    *,
    runner: JobEvaluationRunner,
    session_factory: SessionFactory | None = None,
) -> BatchEvaluationResult:
    settings = get_settings()
    limit = payload.limit or settings.evaluation_batch_limit_default
    limit = min(limit, settings.evaluation_batch_limit_max)
    requested_concurrency = payload.concurrency or settings.evaluation_concurrency
    concurrency = min(requested_concurrency, settings.evaluation_concurrency_max)
    if concurrency > 1 and session_factory is None:
        log_event(
            logger,
            "evaluation.batch.concurrency_fallback",
            requested=concurrency,
            reason="no_session_factory",
        )
        concurrency = 1

    jobs = JobRepository(session).list_for_evaluation_batch(
        source=None if payload.source is None else payload.source.value,
        discovered_after=payload.discovered_after,
        discovered_before=payload.discovered_before,
        unevaluated_only=not payload.reevaluate,
        limit=limit,
    )
    job_ids = [job.id for job in jobs]
    log_event(
        logger,
        "evaluation.batch.started",
        discovered=len(job_ids),
        source=None if payload.source is None else payload.source.value,
        dry_run=payload.dry_run,
        reevaluate=payload.reevaluate,
        concurrency=concurrency,
        limit=limit,
    )

    limiter = RateLimiter(per_minute=settings.evaluation_rate_limit_per_minute)
    outcomes: list[_JobOutcome] = []

    if concurrency == 1:
        for job_id in job_ids:
            outcomes.append(
                _process_job(
                    session,
                    job_id,
                    runner=runner,
                    dry_run=payload.dry_run,
                    rate_limiter=limiter,
                )
            )
    else:
        assert session_factory is not None

        def worker(job_id: uuid.UUID) -> _JobOutcome:
            worker_session = session_factory()
            try:
                return _process_job(
                    worker_session,
                    job_id,
                    runner=runner,
                    dry_run=payload.dry_run,
                    rate_limiter=limiter,
                )
            finally:
                worker_session.close()

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(worker, job_id): job_id for job_id in job_ids}
            for future in as_completed(futures):
                job_id = futures[future]
                try:
                    outcomes.append(future.result())
                except Exception as exc:
                    log_exception(
                        logger,
                        "evaluation.batch.job_failed",
                        job_id=str(job_id),
                        stage="worker",
                        detail=str(exc),
                    )
                    outcomes.append(
                        _JobOutcome(
                            error=BatchEvaluationError(
                                job_id=job_id,
                                stage="worker",
                                detail=str(exc),
                            )
                        )
                    )

    summary = _summarize(job_ids, outcomes, dry_run=payload.dry_run)
    log_event(
        logger,
        "evaluation.batch.completed",
        discovered=summary.discovered,
        hard_filtered=summary.hard_filtered,
        evaluated=summary.evaluated,
        apply=summary.apply,
        review=summary.review,
        reject=summary.reject,
        errors=len(summary.errors),
        dry_run=summary.dry_run,
    )
    return summary


def _process_job(
    session: Session,
    job_id: uuid.UUID,
    *,
    runner: JobEvaluationRunner,
    dry_run: bool,
    rate_limiter: RateLimiter,
) -> _JobOutcome:
    try:
        inputs = load_evaluation_inputs(session, job_id)
    except Exception as exc:
        session.rollback()
        log_exception(
            logger,
            "evaluation.batch.job_failed",
            job_id=str(job_id),
            stage="retrieve",
            detail=str(exc),
        )
        return _JobOutcome(
            error=BatchEvaluationError(job_id=job_id, stage="retrieve", detail=str(exc))
        )

    if not inputs.hard_filter.passed:
        log_event(
            logger,
            "evaluation.batch.hard_filtered",
            job_id=str(job_id),
            failed_rules=[str(rule) for rule in inputs.hard_filter.failed_rules],
            dry_run=dry_run,
        )
        if not dry_run:
            try:
                grounded = ground_evaluation(
                    evaluation_from_hard_filter_failure(inputs.hard_filter),
                    allowed_evidence_ids=set(inputs.context.allowed_evidence_ids),
                    evidence=inputs.evidence,
                    hard_filter=inputs.hard_filter,
                )
                persist_evaluation(
                    session,
                    grounded,
                    job_id=inputs.job.id,
                    profile_id=inputs.profile.id,
                    hard_filter=inputs.hard_filter,
                    model=HARD_FILTER_MODEL,
                )
            except Exception as exc:
                session.rollback()
                log_exception(
                    logger,
                    "evaluation.batch.job_failed",
                    job_id=str(job_id),
                    stage="persist",
                    detail=str(exc),
                )
                return _JobOutcome(
                    error=BatchEvaluationError(job_id=job_id, stage="persist", detail=str(exc))
                )
        return _JobOutcome(hard_filtered=True)

    if dry_run:
        log_event(logger, "evaluation.batch.dry_run_skip_agent", job_id=str(job_id))
        return _JobOutcome(evaluated=True)

    try:
        rate_limiter.acquire()
        raw, usage = unwrap_evaluation_run(runner.evaluate(inputs.user_input, inputs.context))
        grounded = ground_evaluation(
            raw,
            allowed_evidence_ids=set(inputs.context.allowed_evidence_ids),
            evidence=inputs.evidence,
            hard_filter=inputs.hard_filter,
        )
        persist_evaluation(
            session,
            grounded,
            job_id=inputs.job.id,
            profile_id=inputs.profile.id,
            hard_filter=inputs.hard_filter,
            model=get_settings().openai_model,
            usage=usage,
        )
        log_event(
            logger,
            "evaluation.batch.evaluated",
            job_id=str(job_id),
            recommendation=grounded.recommendation.value,
            input_tokens=None if usage is None else usage.input_tokens,
            output_tokens=None if usage is None else usage.output_tokens,
            estimated_cost_usd=None if usage is None else usage.estimated_cost_usd,
        )
        return _JobOutcome(evaluated=True, recommendation=grounded.recommendation, usage=usage)
    except Exception as exc:
        session.rollback()
        stage = "agent"
        if isinstance(exc, EvaluationGroundingError):
            stage = "grounding"
        elif isinstance(exc, EvaluationAgentError):
            stage = "agent"
        log_exception(
            logger,
            "evaluation.batch.job_failed",
            job_id=str(job_id),
            stage=stage,
            detail=str(exc),
        )
        return _JobOutcome(error=BatchEvaluationError(job_id=job_id, stage=stage, detail=str(exc)))


def _summarize(
    job_ids: list[uuid.UUID],
    outcomes: list[_JobOutcome],
    *,
    dry_run: bool,
) -> BatchEvaluationResult:
    hard_filtered = 0
    evaluated = 0
    apply = 0
    review = 0
    reject = 0
    errors: list[BatchEvaluationError] = []
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    requests = 0
    cost = 0.0
    saw_cost = False

    for outcome in outcomes:
        if outcome.error is not None:
            errors.append(outcome.error)
            continue
        if outcome.hard_filtered:
            hard_filtered += 1
            continue
        if outcome.evaluated:
            evaluated += 1
            if outcome.recommendation is Recommendation.APPLY:
                apply += 1
            elif outcome.recommendation is Recommendation.REVIEW:
                review += 1
            elif outcome.recommendation is Recommendation.REJECT:
                reject += 1
            if outcome.usage is not None:
                input_tokens += outcome.usage.input_tokens
                output_tokens += outcome.usage.output_tokens
                total_tokens += outcome.usage.total_tokens
                requests += outcome.usage.requests
                if outcome.usage.estimated_cost_usd is not None:
                    cost += outcome.usage.estimated_cost_usd
                    saw_cost = True

    return BatchEvaluationResult(
        discovered=len(job_ids),
        hard_filtered=hard_filtered,
        evaluated=evaluated,
        apply=apply,
        review=review,
        reject=reject,
        errors=errors,
        dry_run=dry_run,
        usage=ModelUsageSummary(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            requests=requests,
            estimated_cost_usd=round(cost, 6) if saw_cost else None,
        ),
    )
