"""Job ingestion use cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import EmploymentType, JobSource, RemotePolicy, Seniority
from app.models.job import Job
from app.repositories.jobs import JobListFilters, JobRepository
from app.schemas.job import JobCreate, JobListResponse, JobRead
from app.services.job_hashing import job_content_hash


class DuplicateJobError(ValueError):
    """Raised when source + source_job_id already exists."""


class JobNotFoundError(LookupError):
    """Raised when a job id is not in the database."""


def create_job(session: Session, payload: JobCreate) -> JobRead:
    repo = JobRepository(session)
    existing = repo.get_by_source_identity(payload.source.value, payload.source_job_id)
    if existing is not None:
        raise DuplicateJobError(payload.source_job_id)

    job = _new_job(payload)
    try:
        repo.add(job)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateJobError(payload.source_job_id) from exc

    session.refresh(job)
    duplicates = repo.ids_with_content_hash(job.content_hash, exclude_id=job.id)
    return _to_read(job, duplicates)


def upsert_job(session: Session, payload: JobCreate) -> tuple[JobRead, str]:
    """Insert or update by source + source_job_id. Used by board sync."""
    repo = JobRepository(session)
    existing = repo.get_by_source_identity(payload.source.value, payload.source_job_id)
    if existing is None:
        job = _new_job(payload)
        try:
            repo.add(job)
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            existing = repo.get_by_source_identity(payload.source.value, payload.source_job_id)
            if existing is None:
                raise DuplicateJobError(payload.source_job_id) from exc
            _apply_payload(existing, payload, preserve_discovered_at=True)
            session.commit()
            session.refresh(existing)
            duplicates = repo.ids_with_content_hash(existing.content_hash, exclude_id=existing.id)
            return _to_read(existing, duplicates), "updated"
        session.refresh(job)
        duplicates = repo.ids_with_content_hash(job.content_hash, exclude_id=job.id)
        return _to_read(job, duplicates), "inserted"

    _apply_payload(existing, payload, preserve_discovered_at=True)
    session.commit()
    session.refresh(existing)
    duplicates = repo.ids_with_content_hash(existing.content_hash, exclude_id=existing.id)
    return _to_read(existing, duplicates), "updated"


def _new_job(payload: JobCreate) -> Job:
    job = Job(id=uuid.uuid4(), discovered_at=payload.discovered_at or datetime.now(UTC))
    _apply_payload(job, payload, preserve_discovered_at=False)
    return job


def _apply_payload(job: Job, payload: JobCreate, *, preserve_discovered_at: bool) -> None:
    job.source = payload.source.value
    job.source_job_id = payload.source_job_id
    job.company = payload.company
    job.title = payload.title
    job.description = payload.description
    job.location = payload.location
    job.remote_policy = payload.remote_policy.value if payload.remote_policy else None
    job.employment_type = payload.employment_type.value if payload.employment_type else None
    job.seniority = payload.seniority.value if payload.seniority else None
    job.salary_min = payload.salary_min
    job.salary_max = payload.salary_max
    job.salary_currency = payload.salary_currency
    job.job_url = payload.job_url
    job.application_url = payload.application_url
    job.department = payload.department
    job.posted_at = payload.posted_at
    if not preserve_discovered_at:
        job.discovered_at = payload.discovered_at or job.discovered_at or datetime.now(UTC)
    job.raw_data = payload.raw_data
    job.content_hash = job_content_hash(payload.description)


def get_job(session: Session, job_id: uuid.UUID) -> JobRead:
    repo = JobRepository(session)
    job = repo.get_by_id(job_id)
    if job is None:
        raise JobNotFoundError(str(job_id))
    duplicates = repo.ids_with_content_hash(job.content_hash, exclude_id=job.id)
    return _to_read(job, duplicates)


def list_jobs(
    session: Session,
    filters: JobListFilters,
    *,
    limit: int,
    offset: int,
) -> JobListResponse:
    repo = JobRepository(session)
    items, total = repo.list_page(filters, limit=limit, offset=offset)
    dup_hashes = repo.hashes_with_duplicates({job.content_hash for job in items})
    ids_by_hash: dict[str, list[uuid.UUID]] = {}
    for job in items:
        if job.content_hash in dup_hashes and job.content_hash not in ids_by_hash:
            ids_by_hash[job.content_hash] = repo.ids_with_content_hash(job.content_hash)
    return JobListResponse(
        items=[
            _to_read(
                job,
                [job_id for job_id in ids_by_hash.get(job.content_hash, []) if job_id != job.id],
            )
            for job in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def _to_read(job: Job, duplicate_ids: list[uuid.UUID]) -> JobRead:
    return JobRead(
        id=job.id,
        source=JobSource(job.source),
        source_job_id=job.source_job_id,
        company=job.company,
        title=job.title,
        description=job.description,
        location=job.location,
        remote_policy=RemotePolicy(job.remote_policy) if job.remote_policy else None,
        employment_type=EmploymentType(job.employment_type) if job.employment_type else None,
        seniority=Seniority(job.seniority) if job.seniority else None,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        job_url=job.job_url,
        application_url=job.application_url,
        department=job.department,
        posted_at=job.posted_at,
        discovered_at=job.discovered_at,
        raw_data=dict(job.raw_data),
        content_hash=job.content_hash,
        is_duplicate_description=bool(duplicate_ids),
        duplicate_description_job_ids=duplicate_ids,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
