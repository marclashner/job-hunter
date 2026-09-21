"""Greenhouse Job Board JSON API client (boards-api.greenhouse.io)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.enums import EmploymentType, JobSource
from app.schemas.job import JobCreate
from app.sources.base import (
    JobBoardNotFoundError,
    JobNormalizationError,
    JobSourceFetchError,
    RawJob,
)
from app.sources.fields import (
    as_job_id,
    as_string,
    clip,
    employment_from_text,
    parse_datetime,
    remote_policy_from_text,
    seniority_from_title,
)
from app.sources.html_text import html_to_text
from app.sources.http import RetryingJsonClient

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://boards-api.greenhouse.io"


class GreenhouseClient:
    """Reads Greenhouse's public JSON job-board API. Does not scrape HTML."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout | float | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = RetryingJsonClient(
            client,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            sleep=sleep,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GreenhouseClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_board(self, board_token: str) -> dict[str, Any]:
        payload = self._get_json(f"/v1/boards/{board_token}", item=False)
        if not isinstance(payload, dict):
            raise JobSourceFetchError("Greenhouse board response was not an object")
        return payload

    def get_job(self, board_token: str, job_id: str) -> dict[str, Any]:
        payload = self._get_json(f"/v1/boards/{board_token}/jobs/{job_id}", item=True)
        if not isinstance(payload, dict):
            raise JobNormalizationError("Greenhouse job response was not an object")
        return payload

    def list_jobs(self, board_token: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/v1/boards/{board_token}/jobs",
            params={"content": "true"},
            item=False,
        )
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise JobSourceFetchError("Greenhouse jobs response was missing a jobs array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise JobSourceFetchError("Greenhouse jobs field was not a list")
        return [item for item in jobs if isinstance(item, dict)]

    def fetch_jobs(self, company_identifier: str) -> list[RawJob]:
        board = self.get_board(company_identifier)
        company_name = as_string(board.get("name")) or company_identifier
        raw_jobs: list[RawJob] = []
        for item in self.list_jobs(company_identifier):
            payload = item
            if not as_string(payload.get("content")):
                job_id = as_job_id(payload)
                if job_id is None:
                    logger.warning(
                        "Skipping Greenhouse row without id or content board=%s",
                        company_identifier,
                    )
                    continue
                try:
                    payload = self.get_job(company_identifier, job_id)
                except (JobNormalizationError, JobSourceFetchError, httpx.HTTPError):
                    logger.exception(
                        "Skipping Greenhouse job that failed individual fetch board=%s id=%s",
                        company_identifier,
                        job_id,
                    )
                    continue
            raw_jobs.append(
                RawJob(
                    source=JobSource.GREENHOUSE,
                    company_identifier=company_identifier,
                    company_name=company_name,
                    payload=payload,
                )
            )
        return raw_jobs

    def normalize(self, raw_job: RawJob) -> JobCreate:
        payload = raw_job.payload
        job_id = as_job_id(payload)
        title = as_string(payload.get("title"))
        description = html_to_text(as_string(payload.get("content")) or "")
        if not job_id or not title or not description:
            raise JobNormalizationError("Greenhouse job is missing id, title, or description")

        absolute_url = as_string(payload.get("absolute_url"))
        location = _location_name(payload)
        return JobCreate(
            source=JobSource.GREENHOUSE,
            source_job_id=job_id[:255],
            company=raw_job.company_name[:255],
            title=title[:255],
            description=description,
            location=clip(location, 255),
            remote_policy=remote_policy_from_text(location),
            employment_type=_employment_type(payload),
            seniority=seniority_from_title(title),
            job_url=clip(absolute_url, 2048),
            application_url=clip(absolute_url, 2048),
            department=_department_name(payload),
            posted_at=_posted_at(payload),
            raw_data={
                "source": JobSource.GREENHOUSE.value,
                "board_token": raw_job.company_identifier,
                "greenhouse_job_id": job_id,
                "fetched_at": datetime.now(UTC).isoformat(),
                "api": "boards-api.greenhouse.io/v1",
                "payload": payload,
            },
        )

    def _get_json(
        self,
        path: str,
        params: dict[str, str] | None = None,
        *,
        item: bool,
    ) -> Any:
        status, payload = self._http.get_json(path, params=params)
        if status == 404:
            if item:
                raise JobNormalizationError(f"Greenhouse job not found: {path}")
            raise JobBoardNotFoundError(f"Greenhouse board not found: {path}")
        return payload


def _location_name(payload: dict[str, Any]) -> str | None:
    location = payload.get("location")
    if isinstance(location, dict):
        name = as_string(location.get("name"))
        if name:
            return name
    offices = payload.get("offices")
    if isinstance(offices, list):
        names: list[str] = []
        for office in offices:
            if isinstance(office, dict):
                name = as_string(office.get("name"))
                if name:
                    names.append(name)
        if names:
            return ", ".join(names)
    return None


def _department_name(payload: dict[str, Any]) -> str | None:
    departments = payload.get("departments")
    if not isinstance(departments, list):
        return None
    for department in departments:
        if isinstance(department, dict):
            name = as_string(department.get("name"))
            if name:
                return name[:255]
    return None


def _posted_at(payload: dict[str, Any]) -> datetime | None:
    for key in ("first_published", "updated_at", "created_at"):
        parsed = parse_datetime(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _employment_type(payload: dict[str, Any]) -> EmploymentType | None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, list):
        return None
    for item in metadata:
        if not isinstance(item, dict):
            continue
        name = (as_string(item.get("name")) or "").lower()
        if "employ" not in name:
            continue
        mapped = employment_from_text(as_string(item.get("value")))
        if mapped is not None:
            return mapped
    return None
