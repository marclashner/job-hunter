"""Job ingestion and evaluation HTTP API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.grounding import EvaluationGroundingError
from app.agents.job_evaluation import (
    EvaluationAgentError,
    EvaluationConfigurationError,
    JobEvaluationRunner,
)
from app.api.deps import get_db, get_evaluation_runner
from app.models.enums import JobSource, RemotePolicy, Seniority
from app.repositories.jobs import JobListFilters
from app.schemas.evaluation import JobEvaluationRead
from app.schemas.job import JobCreate, JobListResponse, JobRead
from app.scoring.hard_filters import HardFilterResult
from app.services.candidate import ProfileNotFoundError
from app.services.evaluation import evaluate_job
from app.services.hard_filter import evaluate_job_hard_filter
from app.services.jobs import DuplicateJobError, JobNotFoundError, create_job, get_job, list_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def post_job(
    payload: JobCreate,
    session: Annotated[Session, Depends(get_db)],
) -> JobRead:
    try:
        return create_job(session, payload)
    except DuplicateJobError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job already exists for this source and source_job_id",
        ) from exc


@router.get("", response_model=JobListResponse)
def get_jobs(
    session: Annotated[Session, Depends(get_db)],
    source: Annotated[JobSource | None, Query()] = None,
    title: Annotated[str | None, Query(min_length=1)] = None,
    location: Annotated[str | None, Query(min_length=1)] = None,
    remote_policy: Annotated[RemotePolicy | None, Query()] = None,
    seniority: Annotated[Seniority | None, Query()] = None,
    minimum_salary: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    filters = JobListFilters(
        source=source,
        title=title,
        location=location,
        remote_policy=remote_policy,
        seniority=seniority,
        minimum_salary=minimum_salary,
    )
    return list_jobs(session, filters, limit=limit, offset=offset)


@router.post(
    "/{job_id}/evaluate",
    response_model=JobEvaluationRead,
    status_code=status.HTTP_201_CREATED,
)
def post_job_evaluate(
    job_id: UUID,
    session: Annotated[Session, Depends(get_db)],
    runner: Annotated[JobEvaluationRunner, Depends(get_evaluation_runner)],
) -> JobEvaluationRead:
    try:
        return evaluate_job(session, job_id, runner=runner)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found. Run: uv run python scripts/seed_candidate.py",
        ) from exc
    except EvaluationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except EvaluationGroundingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EvaluationAgentError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.post("/{job_id}/hard-filter", response_model=HardFilterResult)
def post_job_hard_filter(
    job_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> HardFilterResult:
    try:
        return evaluate_job_hard_filter(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except ProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found. Run: uv run python scripts/seed_candidate.py",
        ) from exc


@router.get("/{job_id}", response_model=JobRead)
def get_job_by_id(
    job_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> JobRead:
    try:
        return get_job(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
