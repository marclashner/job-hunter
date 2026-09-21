"""Ingest listings from a JobSource adapter without failing the whole run on one bad row."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.enums import JobSource
from app.schemas.sources import SourceSyncError, SourceSyncResult
from app.services.jobs import upsert_job
from app.sources.base import JobNormalizationError, JobSourceAdapter, RawJob

logger = logging.getLogger(__name__)


def sync_jobs(
    session: Session,
    adapter: JobSourceAdapter,
    company_identifier: str,
    *,
    source: JobSource,
) -> SourceSyncResult:
    raw_jobs = adapter.fetch_jobs(company_identifier)
    inserted = 0
    updated = 0
    skipped = 0
    errors: list[SourceSyncError] = []

    for raw_job in raw_jobs:
        try:
            payload = adapter.normalize(raw_job)
            _, action = upsert_job(session, payload)
        except JobNormalizationError as exc:
            skipped += 1
            errors.append(
                SourceSyncError(
                    source_job_id=_raw_job_id(raw_job),
                    reason=str(exc) or "malformed job",
                )
            )
            logger.warning(
                "Skipping malformed job source=%s board=%s error=%s",
                source.value,
                company_identifier,
                exc,
            )
            continue
        except Exception:
            skipped += 1
            errors.append(
                SourceSyncError(source_job_id=_raw_job_id(raw_job), reason="ingestion failed")
            )
            logger.exception(
                "Skipping job after unexpected ingestion error source=%s board=%s",
                source.value,
                company_identifier,
            )
            try:
                session.rollback()
            except Exception:
                logger.exception("Failed to rollback after job ingestion error")
            continue
        if action == "inserted":
            inserted += 1
        else:
            updated += 1

    return SourceSyncResult(
        source=source,
        company_identifier=company_identifier,
        fetched=len(raw_jobs),
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


def _raw_job_id(raw_job: RawJob) -> str | None:
    raw = raw_job.payload.get("id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None
