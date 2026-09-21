"""Load a job and the primary candidate, then apply deterministic hard filters."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.jobs import JobRepository
from app.scoring.hard_filters import HardFilterResult, evaluate_hard_filters
from app.services.candidate import PRIMARY_PROFILE_KEY, require_profile
from app.services.jobs import JobNotFoundError


def evaluate_job_hard_filter(
    session: Session,
    job_id: UUID,
    *,
    profile_key: str = PRIMARY_PROFILE_KEY,
) -> HardFilterResult:
    job = JobRepository(session).get_by_id(job_id)
    if job is None:
        raise JobNotFoundError(str(job_id))
    profile = require_profile(session, profile_key)
    return evaluate_hard_filters(job, profile)
