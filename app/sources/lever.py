"""Lever public postings JSON API client (api.lever.co)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.enums import JobSource, RemotePolicy
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

DEFAULT_BASE_URL = "https://api.lever.co"
_DEFAULT_PAGE_SIZE = 100
_MAX_PAGES = 50


class LeverClient:
    """Reads Lever's public JSON postings API. Does not scrape HTML."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: httpx.Timeout | float | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> None:
        self._http = RetryingJsonClient(
            client,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            sleep=sleep,
        )
        self._page_size = min(max(page_size, 1), _DEFAULT_PAGE_SIZE)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> LeverClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_job(self, site: str, job_id: str) -> dict[str, Any]:
        payload = self._get_json(f"/v0/postings/{site}/{job_id}", item=True)
        if not isinstance(payload, dict):
            raise JobNormalizationError("Lever posting response was not an object")
        return payload

    def list_jobs(self, site: str) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        skip = 0
        for _ in range(_MAX_PAGES):
            payload = self._get_json(
                f"/v0/postings/{site}",
                params={
                    "mode": "json",
                    "limit": str(self._page_size),
                    "skip": str(skip),
                },
                item=False,
            )
            if not isinstance(payload, list):
                raise JobSourceFetchError("Lever postings response was not a list")
            page = [item for item in payload if isinstance(item, dict)]
            collected.extend(page)
            if len(payload) < self._page_size:
                break
            skip += self._page_size
        return collected

    def fetch_jobs(self, company_identifier: str) -> list[RawJob]:
        raw_jobs: list[RawJob] = []
        for payload in self.list_jobs(company_identifier):
            if as_job_id(payload) is None:
                logger.warning(
                    "Skipping Lever row without id site=%s",
                    company_identifier,
                )
                continue
            raw_jobs.append(
                RawJob(
                    source=JobSource.LEVER,
                    company_identifier=company_identifier,
                    company_name=company_identifier,
                    payload=payload,
                )
            )
        return raw_jobs

    def normalize(self, raw_job: RawJob) -> JobCreate:
        payload = raw_job.payload
        job_id = as_job_id(payload)
        title = as_string(payload.get("text"))
        description = _description(payload)
        if not job_id or not title or not description:
            raise JobNormalizationError("Lever job is missing id, title, or description")

        categories = payload.get("categories")
        categories_dict = categories if isinstance(categories, dict) else {}
        location = as_string(categories_dict.get("location"))
        department = as_string(categories_dict.get("department") or categories_dict.get("team"))
        workplace = as_string(payload.get("workplaceType"))
        hosted_url = as_string(payload.get("hostedUrl"))
        apply_url = as_string(payload.get("applyUrl")) or hosted_url
        return JobCreate(
            source=JobSource.LEVER,
            source_job_id=job_id[:255],
            company=raw_job.company_name[:255],
            title=title[:255],
            description=description,
            location=clip(location, 255),
            remote_policy=_lever_remote_policy(workplace, location),
            employment_type=employment_from_text(as_string(categories_dict.get("commitment"))),
            seniority=seniority_from_title(title)
            or seniority_from_title(as_string(categories_dict.get("level")) or ""),
            job_url=clip(hosted_url, 2048),
            application_url=clip(apply_url, 2048),
            department=clip(department, 255),
            posted_at=parse_datetime(payload.get("createdAt")),
            raw_data={
                "source": JobSource.LEVER.value,
                "site": raw_job.company_identifier,
                "lever_posting_id": job_id,
                "fetched_at": datetime.now(UTC).isoformat(),
                "api": "api.lever.co/v0",
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
                raise JobNormalizationError(f"Lever posting not found: {path}")
            raise JobBoardNotFoundError(f"Lever site not found: {path}")
        return payload


def _description(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    plain = as_string(payload.get("descriptionPlain"))
    if plain:
        parts.append(plain)
    else:
        html = html_to_text(as_string(payload.get("description")) or "")
        if html:
            parts.append(html)
    opening = as_string(payload.get("opening"))
    if opening:
        parts.append(html_to_text(opening) or opening)
    additional = as_string(payload.get("additionalPlain")) or html_to_text(
        as_string(payload.get("additional")) or ""
    )
    if additional:
        parts.append(additional)
    lists = payload.get("lists")
    if isinstance(lists, list):
        for item in lists:
            if not isinstance(item, dict):
                continue
            heading = as_string(item.get("text"))
            body = html_to_text(as_string(item.get("content")) or "")
            chunk = " ".join(part for part in (heading, body) if part)
            if chunk:
                parts.append(chunk)
    return " ".join(parts).strip()


def _lever_remote_policy(workplace: str | None, location: str | None) -> RemotePolicy:
    if workplace:
        lowered = workplace.lower().replace("_", "-")
        if lowered in {"remote"}:
            return RemotePolicy.REMOTE
        if lowered in {"hybrid"}:
            return RemotePolicy.HYBRID
        if lowered in {"on-site", "onsite", "on site"}:
            return RemotePolicy.ONSITE
    return remote_policy_from_text(workplace, location)
