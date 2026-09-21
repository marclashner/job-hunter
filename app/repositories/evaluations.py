"""Queries for stored job evaluations."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation import JobEvaluationRecord


class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: JobEvaluationRecord) -> JobEvaluationRecord:
        self._session.add(record)
        self._session.flush()
        return record

    def get_by_id(self, evaluation_id: uuid.UUID) -> JobEvaluationRecord | None:
        return self._session.get(JobEvaluationRecord, evaluation_id)

    def latest_for_job(self, job_id: uuid.UUID) -> JobEvaluationRecord | None:
        statement = (
            select(JobEvaluationRecord)
            .where(JobEvaluationRecord.job_id == job_id)
            .order_by(JobEvaluationRecord.created_at.desc())
            .limit(1)
        )
        return self._session.scalars(statement).first()
