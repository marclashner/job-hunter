"""Shared retrying JSON GET client for job-board HTTP APIs."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.sources.base import JobSourceFetchError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "autonomous-job-search-agent/0.1"
_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryingJsonClient:
    """httpx wrapper with timeouts, retries, and JSON decoding. Adapters map 404s."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        base_url: str,
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
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def get_json(self, path: str, params: dict[str, str] | None = None) -> tuple[int, Any]:
        response = self._request("GET", f"{self._base_url}{path}", params=params)
        if response.status_code == 404:
            return 404, None
        try:
            return response.status_code, response.json()
        except ValueError as exc:
            raise JobSourceFetchError("Job board returned non-JSON") from exc

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
                    "Job-board request failed attempt=%s url=%s error=%s",
                    attempt + 1,
                    url,
                    exc,
                )
                if attempt >= self._max_retries:
                    break
                self._sleep(_backoff_seconds(attempt))
                continue

            if response.status_code == 404:
                return response
            if response.status_code in _RETRYABLE_STATUS and attempt < self._max_retries:
                logger.warning(
                    "Job-board retryable status=%s attempt=%s url=%s",
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
                    f"Job board HTTP {response.status_code} for {url}"
                ) from exc
            return response

        raise JobSourceFetchError(f"Job board request failed after retries: {url}") from last_error


def _backoff_seconds(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None and retry_after.isdigit():
            delay = float(str(retry_after))
            return delay if delay < 8.0 else 8.0
    delay = 0.25 * (2**attempt)
    return delay if delay < 4.0 else 4.0
