"""Greenhouse HTTP client tests with mocked responses."""

import httpx
import pytest

from app.sources.base import JobBoardNotFoundError
from app.sources.greenhouse import GreenhouseClient
from tests.support.greenhouse import (
    BOARD_TOKEN,
    board_payload,
    greenhouse_client,
    greenhouse_job,
)


def test_fetch_jobs_skips_non_objects_and_loads_board_name() -> None:
    job = greenhouse_job(11)
    http = greenhouse_client(
        {
            f"/v1/boards/{BOARD_TOKEN}": httpx.Response(200, json=board_payload()),
            f"/v1/boards/{BOARD_TOKEN}/jobs": httpx.Response(
                200, json={"jobs": [job, "bogus", {"not": "enough"}], "meta": {"total": 3}}
            ),
        }
    )
    client = GreenhouseClient(http, sleep=lambda _delay: None, max_retries=0)
    try:
        raw_jobs = client.fetch_jobs(BOARD_TOKEN)
    finally:
        client.close()

    # Non-dict rows are dropped; dicts without id/content are skipped without failing the batch.
    assert [item.payload["id"] for item in raw_jobs] == [11]
    assert raw_jobs[0].company_name == "Acme Co"


def test_get_job_returns_individual_listing() -> None:
    job = greenhouse_job(99, title="Staff Platform Engineer")
    http = greenhouse_client({f"/v1/boards/{BOARD_TOKEN}/jobs/99": httpx.Response(200, json=job)})
    client = GreenhouseClient(http, sleep=lambda _delay: None, max_retries=0)
    try:
        payload = client.get_job(BOARD_TOKEN, "99")
    finally:
        client.close()
    assert payload["title"] == "Staff Platform Engineer"


def test_retries_transient_status_then_succeeds() -> None:
    http = greenhouse_client(
        {
            f"/v1/boards/{BOARD_TOKEN}": [
                httpx.Response(503, json={"error": "unavailable"}),
                httpx.Response(200, json=board_payload("Retried Co")),
            ]
        }
    )
    client = GreenhouseClient(http, sleep=lambda _delay: None, max_retries=2)
    try:
        board = client.get_board(BOARD_TOKEN)
    finally:
        client.close()
    assert board["name"] == "Retried Co"


def test_unknown_board_is_not_found() -> None:
    http = greenhouse_client({})
    client = GreenhouseClient(http, sleep=lambda _delay: None, max_retries=0)
    with pytest.raises(JobBoardNotFoundError):
        client.get_board("missing-board")
    client.close()
