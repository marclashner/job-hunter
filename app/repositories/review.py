"""Queries for the review dashboard queue and summary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Subquery

from app.models.enums import JobSource, Recommendation, RemotePolicy
from app.models.evaluation import JobEvaluationRecord
from app.models.job import Job


@dataclass(frozen=True, slots=True)
class ReviewQueueFilters:
    recommendation: Recommendation | None = None
    minimum_score: int | None = None
    source: JobSource | None = None
    remote_policy: RemotePolicy | None = None
    discovered_after: datetime | None = None
    discovered_before: datetime | None = None


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def summary_counts(self, *, today_start: datetime) -> dict[str, int]:
        latest = _latest_evaluations()
        discovered_today = self._session.scalar(
            select(func.count()).select_from(Job).where(Job.discovered_at >= today_start)
        )
        evaluated = self._session.scalar(select(func.count()).select_from(latest))
        recommended = self._session.scalar(
            select(func.count())
            .select_from(latest)
            .where(latest.c.recommendation == Recommendation.APPLY.value)
        )
        needing_review = self._session.scalar(
            select(func.count())
            .select_from(latest)
            .where(latest.c.recommendation == Recommendation.REVIEW.value)
        )
        return {
            "discovered_today": int(discovered_today or 0),
            "evaluated": int(evaluated or 0),
            "recommended_applications": int(recommended or 0),
            "needing_review": int(needing_review or 0),
        }

    def list_queue(
        self,
        filters: ReviewQueueFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[Job, JobEvaluationRecord | None]], int]:
        latest = _latest_evaluations()
        joined = (
            select(Job.id)
            .join(latest, latest.c.job_id == Job.id)
            .join(JobEvaluationRecord, JobEvaluationRecord.id == latest.c.id)
        )
        filtered_ids = _apply_queue_filters(joined, filters)
        total = self._session.scalar(select(func.count()).select_from(filtered_ids.subquery()))
        rows = (
            select(Job, JobEvaluationRecord)
            .join(latest, latest.c.job_id == Job.id)
            .join(JobEvaluationRecord, JobEvaluationRecord.id == latest.c.id)
        )
        filtered = _apply_queue_filters(rows, filters)
        rec_order = case(
            (JobEvaluationRecord.recommendation == Recommendation.APPLY.value, 0),
            (JobEvaluationRecord.recommendation == Recommendation.REVIEW.value, 1),
            (JobEvaluationRecord.recommendation == Recommendation.REJECT.value, 2),
            else_=3,
        )
        items = list(
            self._session.execute(
                filtered.order_by(
                    rec_order,
                    JobEvaluationRecord.overall_score.desc().nulls_last(),
                    Job.discovered_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return [(job, evaluation) for job, evaluation in items], int(total or 0)


def _latest_evaluations() -> Subquery:
    ranked = (
        select(
            JobEvaluationRecord.id,
            JobEvaluationRecord.job_id,
            JobEvaluationRecord.recommendation,
            func.row_number()
            .over(
                partition_by=JobEvaluationRecord.job_id,
                order_by=JobEvaluationRecord.created_at.desc(),
            )
            .label("rn"),
        )
    ).subquery()
    return select(ranked).where(ranked.c.rn == 1).subquery()


def _apply_queue_filters(statement: Select[Any], filters: ReviewQueueFilters) -> Select[Any]:
    if filters.source is not None:
        statement = statement.where(Job.source == filters.source.value)
    if filters.remote_policy is not None:
        statement = statement.where(Job.remote_policy == filters.remote_policy.value)
    if filters.discovered_after is not None:
        statement = statement.where(Job.discovered_at >= filters.discovered_after)
    if filters.discovered_before is not None:
        statement = statement.where(Job.discovered_at <= filters.discovered_before)
    if filters.recommendation is not None:
        statement = statement.where(
            JobEvaluationRecord.recommendation == filters.recommendation.value
        )
    if filters.minimum_score is not None:
        statement = statement.where(JobEvaluationRecord.overall_score >= filters.minimum_score)
    return statement
