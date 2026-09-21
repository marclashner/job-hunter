"""Review dashboard: queue, detail, and human decisions. Does not submit applications."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.enums import HumanDecision, JobSource, Recommendation, RemotePolicy
from app.models.evaluation import JobEvaluationRecord
from app.models.job import Job
from app.repositories.evaluations import EvaluationRepository
from app.repositories.jobs import JobRepository
from app.repositories.review import ReviewQueueFilters, ReviewRepository
from app.schemas.candidate import CandidateEvidenceRead
from app.schemas.evaluation import JobEvaluationRead
from app.schemas.review import JobQueueItem, JobQueueResponse, JobReviewDetail, ReviewSummary
from app.services.candidate import PRIMARY_PROFILE_KEY, evidence_to_read, require_profile
from app.services.evaluation import evaluation_record_to_read
from app.services.jobs import JobNotFoundError, get_job


def review_summary(session: Session, *, now: datetime | None = None) -> ReviewSummary:
    current = now or datetime.now(UTC)
    today_start = current.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    counts = ReviewRepository(session).summary_counts(today_start=today_start)
    return ReviewSummary(
        discovered_today=counts["discovered_today"],
        evaluated=counts["evaluated"],
        recommended_applications=counts["recommended_applications"],
        needing_review=counts["needing_review"],
        applications_submitted=0,
        interviews=0,
        offers=0,
    )


def list_review_queue(
    session: Session,
    filters: ReviewQueueFilters,
    *,
    limit: int,
    offset: int,
) -> JobQueueResponse:
    items, total = ReviewRepository(session).list_queue(filters, limit=limit, offset=offset)
    return JobQueueResponse(
        items=[_queue_item(job, evaluation) for job, evaluation in items],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_review_detail(session: Session, job_id: UUID) -> JobReviewDetail:
    job = get_job(session, job_id)
    record = EvaluationRepository(session).latest_for_job(job_id)
    evaluation = None if record is None else evaluation_record_to_read(record)
    hard_filter = None if evaluation is None else evaluation.hard_filter
    evidence = _supporting_evidence(session, evaluation)
    return JobReviewDetail(
        job=job,
        evaluation=evaluation,
        supporting_evidence=evidence,
        hard_filter=hard_filter,
        application_url=job.application_url,
        human_decision=job.human_decision,
    )


def set_human_decision(session: Session, job_id: UUID, decision: HumanDecision) -> JobReviewDetail:
    job_row = JobRepository(session).get_by_id(job_id)
    if job_row is None:
        raise JobNotFoundError(str(job_id))
    job_row.human_decision = decision.value
    job_row.human_decided_at = datetime.now(UTC)
    session.commit()
    return get_review_detail(session, job_id)


def discovered_day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1) - timedelta(microseconds=1)


def _supporting_evidence(
    session: Session,
    evaluation: JobEvaluationRead | None,
) -> list[CandidateEvidenceRead]:
    if evaluation is None:
        return []
    wanted = set(evaluation.supporting_evidence_ids)
    if not wanted:
        return []
    profile = require_profile(session, PRIMARY_PROFILE_KEY)
    return [evidence_to_read(item) for item in profile.evidence if item.id in wanted]


def _queue_item(job: Job, evaluation: JobEvaluationRecord | None) -> JobQueueItem:
    return JobQueueItem(
        id=job.id,
        company=job.company,
        title=job.title,
        location=job.location,
        compensation=_compensation(job),
        score=None if evaluation is None else evaluation.overall_score,
        recommendation=None if evaluation is None else Recommendation(evaluation.recommendation),
        top_strengths=[] if evaluation is None else list(evaluation.strengths)[:3],
        concerns=[] if evaluation is None else list(evaluation.concerns)[:3],
        source=JobSource(job.source),
        remote_policy=RemotePolicy(job.remote_policy) if job.remote_policy else None,
        discovered_at=job.discovered_at,
        human_decision=HumanDecision(job.human_decision) if job.human_decision else None,
        application_url=job.application_url,
    )


def _compensation(job: Job) -> str:
    currency = job.salary_currency or "USD"
    if job.salary_min is None and job.salary_max is None:
        return "Unlisted"
    if job.salary_min is not None and job.salary_max is not None:
        return f"{job.salary_min:,}-{job.salary_max:,} {currency}"
    if job.salary_min is not None:
        return f"{job.salary_min:,}+ {currency}"
    return f"up to {job.salary_max:,} {currency}"
