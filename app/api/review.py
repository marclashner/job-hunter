"""Human review dashboard HTTP API. Decisions do not submit applications."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import JobSource, Recommendation, RemotePolicy
from app.repositories.review import ReviewQueueFilters
from app.schemas.review import (
    HumanDecisionRequest,
    JobQueueResponse,
    JobReviewDetail,
    ReviewSummary,
)
from app.services.jobs import JobNotFoundError
from app.services.review import (
    discovered_day_bounds,
    get_review_detail,
    list_review_queue,
    review_summary,
    set_human_decision,
)

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/summary", response_model=ReviewSummary)
def get_review_summary(session: Annotated[Session, Depends(get_db)]) -> ReviewSummary:
    return review_summary(session)


@router.get("/jobs", response_model=JobQueueResponse)
def get_review_queue(
    session: Annotated[Session, Depends(get_db)],
    recommendation: Annotated[Recommendation | None, Query()] = None,
    minimum_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    source: Annotated[JobSource | None, Query()] = None,
    remote_policy: Annotated[RemotePolicy | None, Query()] = None,
    discovered: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobQueueResponse:
    discovered_after = None
    discovered_before = None
    if discovered is not None:
        discovered_after, discovered_before = discovered_day_bounds(discovered)
    filters = ReviewQueueFilters(
        recommendation=recommendation,
        minimum_score=minimum_score,
        source=source,
        remote_policy=remote_policy,
        discovered_after=discovered_after,
        discovered_before=discovered_before,
    )
    return list_review_queue(session, filters, limit=limit, offset=offset)


@router.get("/jobs/{job_id}", response_model=JobReviewDetail)
def get_review_job(
    job_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> JobReviewDetail:
    try:
        return get_review_detail(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc


@router.post("/jobs/{job_id}/decision", response_model=JobReviewDetail)
def post_review_decision(
    job_id: UUID,
    payload: HumanDecisionRequest,
    session: Annotated[Session, Depends(get_db)],
) -> JobReviewDetail:
    try:
        return set_human_decision(session, job_id, payload.decision)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
