"""Lever HTTP client tests with mocked responses."""

import httpx
import pytest

from app.sources.base import JobBoardNotFoundError
from app.sources.lever import LeverClient
from tests.support.lever import SITE, lever_client, lever_posting


def test_fetch_jobs_skips_non_objects_and_rows_without_ids() -> None:
    posting = lever_posting("p-11")
    http = lever_client(
        {f"/v0/postings/{SITE}": httpx.Response(200, json=[posting, "bogus", {"text": "no-id"}])}
    )
    client = LeverClient(http, sleep=lambda _delay: None, max_retries=0)
    try:
        raw_jobs = client.fetch_jobs(SITE)
    finally:
        client.close()
    assert [item.payload["id"] for item in raw_jobs] == ["p-11"]
    assert raw_jobs[0].company_name == SITE


def test_list_jobs_follows_pagination() -> None:
    first = lever_posting("p-1", title="Senior Backend Engineer")
    second = lever_posting("p-2", title="Staff Platform Engineer")
    third = lever_posting("p-3", title="Junior Support Engineer")
    http = lever_client(
        {
            f"/v0/postings/{SITE}": [
                httpx.Response(200, json=[first, second]),
                httpx.Response(200, json=[third]),
            ]
        }
    )
    client = LeverClient(http, sleep=lambda _delay: None, max_retries=0, page_size=2)
    try:
        jobs = client.list_jobs(SITE)
    finally:
        client.close()
    assert [item["id"] for item in jobs] == ["p-1", "p-2", "p-3"]


def test_get_job_returns_individual_posting() -> None:
    posting = lever_posting("p-99", title="Staff Platform Engineer")
    http = lever_client({f"/v0/postings/{SITE}/p-99": httpx.Response(200, json=posting)})
    client = LeverClient(http, sleep=lambda _delay: None, max_retries=0)
    try:
        payload = client.get_job(SITE, "p-99")
    finally:
        client.close()
    assert payload["text"] == "Staff Platform Engineer"


def test_unknown_site_is_not_found() -> None:
    http = lever_client({})
    client = LeverClient(http, sleep=lambda _delay: None, max_retries=0)
    with pytest.raises(JobBoardNotFoundError):
        client.list_jobs("missing-site")
    client.close()
