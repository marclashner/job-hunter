"""Job ingestion HTTP API. External source adapters are not implemented yet."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import JobSource, RemotePolicy, Seniority
from app.repositories.jobs import JobListFilters
from app.schemas.job import JobCreate, JobListResponse, JobRead
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


@router.get("/{job_id}", response_model=JobRead)
def get_job_by_id(
    job_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> JobRead:
    try:
        return get_job(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
