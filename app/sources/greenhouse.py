"""Greenhouse Job Board JSON API client (boards-api.greenhouse.io)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.enums import EmploymentType, JobSource, RemotePolicy, Seniority
from app.schemas.job import JobCreate
from app.sources.base import (
    JobBoardNotFoundError,
    JobNormalizationError,
    JobSourceFetchError,
    RawJob,
)
from app.sources.html_text import html_to_text

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://boards-api.greenhouse.io"
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
_TITLE_SENIORITY: tuple[tuple[str, Seniority], ...] = (
    ("distinguished", Seniority.DISTINGUISHED),
    ("principal", Seniority.PRINCIPAL),
    ("staff", Seniority.STAFF),
    ("senior", Seniority.SENIOR),
    ("sr.", Seniority.SENIOR),
    ("sr ", Seniority.SENIOR),
    ("junior", Seniority.JUNIOR),
    ("jr.", Seniority.JUNIOR),
    ("jr ", Seniority.JUNIOR),
    ("intern", Seniority.JUNIOR),
)


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
        self._base_url = base_url.rstrip("/")
        self._max_retries = max(0, max_retries)
        self._sleep = sleep
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout if timeout is not None else DEFAULT_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "autonomous-job-search-agent/0.1"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GreenhouseClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_board(self, board_token: str) -> dict[str, Any]:
        payload = self._get_json(f"/v1/boards/{board_token}")
        if not isinstance(payload, dict):
            raise JobSourceFetchError("Greenhouse board response was not an object")
        return payload

    def get_job(self, board_token: str, job_id: str) -> dict[str, Any]:
        payload = self._get_json(f"/v1/boards/{board_token}/jobs/{job_id}")
        if not isinstance(payload, dict):
            raise JobNormalizationError("Greenhouse job response was not an object")
        return payload

    def list_jobs(self, board_token: str) -> list[dict[str, Any]]:
        payload = self._get_json(f"/v1/boards/{board_token}/jobs", params={"content": "true"})
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise JobSourceFetchError("Greenhouse jobs response was missing a jobs array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise JobSourceFetchError("Greenhouse jobs field was not a list")
        return [item for item in jobs if isinstance(item, dict)]

    def fetch_jobs(self, company_identifier: str) -> list[RawJob]:
        board = self.get_board(company_identifier)
        company_name = _string(board.get("name")) or company_identifier
        raw_jobs: list[RawJob] = []
        for item in self.list_jobs(company_identifier):
            payload = item
            if not _string(payload.get("content")):
                job_id = _job_id(payload)
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
        job_id = _job_id(payload)
        title = _string(payload.get("title"))
        description = html_to_text(_string(payload.get("content")) or "")
        if not job_id or not title or not description:
            raise JobNormalizationError("Greenhouse job is missing id, title, or description")

        absolute_url = _string(payload.get("absolute_url"))
        location = _location_name(payload)
        return JobCreate(
            source=JobSource.GREENHOUSE,
            source_job_id=job_id[:255],
            company=raw_job.company_name[:255],
            title=title[:255],
            description=description,
            location=location[:255] if location else None,
            remote_policy=_remote_policy(location),
            employment_type=_employment_type(payload),
            seniority=_seniority_from_title(title),
            job_url=absolute_url[:2048] if absolute_url else None,
            application_url=absolute_url[:2048] if absolute_url else None,
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

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        response = self._request("GET", f"{self._base_url}{path}", params=params)
        try:
            return response.json()
        except ValueError as exc:
            raise JobSourceFetchError("Greenhouse returned non-JSON") from exc

    def _request(
        self, method: str, url: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        last_error: Exception | None = None
        attempts = self._max_retries + 1
        for attempt in range(attempts):
            try:
                response = self._client.request(method, url, params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                logger.warning(
                    "Greenhouse request failed attempt=%s url=%s error=%s", attempt + 1, url, exc
                )
                if attempt >= self._max_retries:
                    break
                self._sleep(_backoff_seconds(attempt))
                continue

            if response.status_code == 404:
                if "/jobs/" in url:
                    raise JobNormalizationError(f"Greenhouse job not found: {url}")
                raise JobBoardNotFoundError(f"Greenhouse board not found: {url}")
            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                logger.warning(
                    "Greenhouse retryable status=%s attempt=%s url=%s",
                    response.status_code,
                    attempt + 1,
                    url,
                )
                self._sleep(_backoff_seconds(attempt, response))
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise JobSourceFetchError(
                    f"Greenhouse HTTP {response.status_code} for {url}"
                ) from exc
            return response

        raise JobSourceFetchError(f"Greenhouse request failed after retries: {url}") from last_error


def _backoff_seconds(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None and retry_after.isdigit():
            delay = float(str(retry_after))
            return delay if delay < 8.0 else 8.0
    delay = 0.25 * (2**attempt)
    return delay if delay < 4.0 else 4.0


def _job_id(payload: dict[str, Any]) -> str | None:
    raw = payload.get("id")
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _string(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _location_name(payload: dict[str, Any]) -> str | None:
    location = payload.get("location")
    if isinstance(location, dict):
        name = _string(location.get("name"))
        if name:
            return name
    offices = payload.get("offices")
    if isinstance(offices, list):
        names: list[str] = []
        for office in offices:
            if isinstance(office, dict):
                name = _string(office.get("name"))
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
            name = _string(department.get("name"))
            if name:
                return name[:255]
    return None


def _posted_at(payload: dict[str, Any]) -> datetime | None:
    for key in ("first_published", "updated_at", "created_at"):
        raw = _string(payload.get(key))
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            logger.warning("Ignoring unparsable Greenhouse timestamp %s=%s", key, raw)
    return None


def _remote_policy(location: str | None) -> RemotePolicy:
    if not location:
        return RemotePolicy.UNKNOWN
    lowered = location.lower()
    if "remote" in lowered and "hybrid" in lowered:
        return RemotePolicy.HYBRID
    if "hybrid" in lowered:
        return RemotePolicy.HYBRID
    if "remote" in lowered:
        return RemotePolicy.REMOTE
    if "on-site" in lowered or "onsite" in lowered:
        return RemotePolicy.ONSITE
    return RemotePolicy.ONSITE


def _seniority_from_title(title: str) -> Seniority | None:
    lowered = f" {title.lower()} "
    for needle, seniority in _TITLE_SENIORITY:
        if needle in lowered:
            return seniority
    return None


def _employment_type(payload: dict[str, Any]) -> EmploymentType | None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, list):
        return None
    for item in metadata:
        if not isinstance(item, dict):
            continue
        name = (_string(item.get("name")) or "").lower()
        if "employ" not in name:
            continue
        value = _string(item.get("value")) or ""
        lowered = value.lower()
        if "contract" in lowered:
            return EmploymentType.CONTRACT
        if "part" in lowered:
            return EmploymentType.PART_TIME
        if "full" in lowered:
            return EmploymentType.FULL_TIME
    return None
