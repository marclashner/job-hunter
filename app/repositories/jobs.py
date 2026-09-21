"""Job listing queries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import JobSource, RemotePolicy, Seniority
from app.models.evaluation import JobEvaluationRecord
from app.models.job import Job


@dataclass(frozen=True, slots=True)
class JobListFilters:
    source: JobSource | None = None
    title: str | None = None
    location: str | None = None
    remote_policy: RemotePolicy | None = None
    seniority: Seniority | None = None
    minimum_salary: int | None = None


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        return self._session.get(Job, job_id)

    def get_by_source_identity(self, source: str, source_job_id: str) -> Job | None:
        statement = select(Job).where(Job.source == source, Job.source_job_id == source_job_id)
        return self._session.scalars(statement).one_or_none()

    def add(self, job: Job) -> Job:
        self._session.add(job)
        self._session.flush()
        return job

    def ids_with_content_hash(
        self, content_hash: str, *, exclude_id: uuid.UUID | None = None
    ) -> list[uuid.UUID]:
        statement = select(Job.id).where(Job.content_hash == content_hash)
        if exclude_id is not None:
            statement = statement.where(Job.id != exclude_id)
        return list(self._session.scalars(statement).all())

    def hashes_with_duplicates(self, hashes: set[str]) -> set[str]:
        if not hashes:
            return set()
        statement = (
            select(Job.content_hash)
            .where(Job.content_hash.in_(hashes))
            .group_by(Job.content_hash)
            .having(func.count(Job.id) > 1)
        )
        return set(self._session.scalars(statement).all())

    def list_for_evaluation_batch(
        self,
        *,
        source: str | None,
        discovered_after: datetime | None,
        discovered_before: datetime | None,
        unevaluated_only: bool,
        limit: int,
    ) -> list[Job]:
        statement = select(Job)
        if source is not None:
            statement = statement.where(Job.source == source)
        if discovered_after is not None:
            statement = statement.where(Job.discovered_at >= discovered_after)
        if discovered_before is not None:
            statement = statement.where(Job.discovered_at <= discovered_before)
        if unevaluated_only:
            evaluated_ids = select(JobEvaluationRecord.job_id).distinct()
            statement = statement.where(Job.id.not_in(evaluated_ids))
        return list(
            self._session.scalars(
                statement.order_by(Job.discovered_at.desc(), Job.created_at.desc()).limit(limit)
            ).all()
        )

    def list_page(
        self,
        filters: JobListFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Job], int]:
        filtered = _apply_filters(select(Job), filters)
        total = self._session.scalar(_apply_filters(select(func.count()).select_from(Job), filters))
        items = list(
            self._session.scalars(
                filtered.order_by(Job.discovered_at.desc(), Job.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return items, int(total or 0)


def _apply_filters(statement: Select[Any], filters: JobListFilters) -> Select[Any]:
    if filters.source is not None:
        statement = statement.where(Job.source == filters.source.value)
    if filters.title:
        statement = statement.where(Job.title.icontains(filters.title, autoescape=True))
    if filters.location:
        statement = statement.where(
            Job.location.is_not(None),
            Job.location.icontains(filters.location, autoescape=True),
        )
    if filters.remote_policy is not None:
        statement = statement.where(Job.remote_policy == filters.remote_policy.value)
    if filters.seniority is not None:
        statement = statement.where(Job.seniority == filters.seniority.value)
    if filters.minimum_salary is not None:
        statement = statement.where(
            or_(
                Job.salary_min >= filters.minimum_salary,
                Job.salary_max >= filters.minimum_salary,
            )
        )
    return statement
