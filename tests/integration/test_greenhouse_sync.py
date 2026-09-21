"""Greenhouse sync against mocked HTTP and live PostgreSQL."""

from collections.abc import Iterator

import httpx
from fastapi.testclient import TestClient

from app.api.sources import get_greenhouse_client
from app.config import get_settings
from app.db import Database
from app.main import app
from app.models.enums import JobSource
from app.repositories.jobs import JobRepository
from app.sources.greenhouse import GreenhouseClient
from tests.support.greenhouse import (
    BOARD_TOKEN,
    board_payload,
    greenhouse_client,
    greenhouse_job,
)
from tests.support.postgres import requires_postgres


def _client_for(responses: dict[str, httpx.Response | list[httpx.Response]]) -> GreenhouseClient:
    return GreenhouseClient(
        greenhouse_client(responses),
        sleep=lambda _delay: None,
        max_retries=1,
    )


def _override_greenhouse(client: GreenhouseClient) -> None:
    def dependency() -> Iterator[GreenhouseClient]:
        yield client

    app.dependency_overrides[get_greenhouse_client] = dependency


@requires_postgres
def test_greenhouse_sync_fetches_normalizes_inserts_and_is_idempotent() -> None:
    job_one = greenhouse_job(91001, title="Senior Backend Engineer")
    job_two = greenhouse_job(
        91002,
        title="Staff Platform Engineer",
        location="New York, NY",
        content="<p>Own Kubernetes platforms and observability.</p>",
    )
    responses = {
        f"/v1/boards/{BOARD_TOKEN}": httpx.Response(200, json=board_payload("Helix Care")),
        f"/v1/boards/{BOARD_TOKEN}/jobs": httpx.Response(200, json={"jobs": [job_one, job_two]}),
    }
    gh_client = _client_for(responses)
    _override_greenhouse(gh_client)
    try:
        with TestClient(app) as test_client:
            first = test_client.post(f"/sources/greenhouse/{BOARD_TOKEN}/sync")
            second = test_client.post(f"/sources/greenhouse/{BOARD_TOKEN}/sync")
            listing = test_client.get("/jobs", params={"source": "greenhouse", "limit": 100})
    finally:
        app.dependency_overrides.pop(get_greenhouse_client, None)
        gh_client.close()

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["source"] == JobSource.GREENHOUSE.value
    assert body["company_identifier"] == BOARD_TOKEN
    assert body["fetched"] == 2
    assert body["inserted"] == 2
    assert body["updated"] == 0
    assert body["skipped"] == 0

    assert second.status_code == 200
    again = second.json()
    assert again["fetched"] == 2
    assert again["inserted"] == 0
    assert again["updated"] == 2

    items = [
        item for item in listing.json()["items"] if item["source_job_id"] in {"91001", "91002"}
    ]
    assert len(items) == 2
    backend = next(item for item in items if item["source_job_id"] == "91001")
    assert backend["company"] == "Helix Care"
    assert backend["source"] == "greenhouse"
    assert "Build Python APIs" in backend["description"]
    assert "<p>" not in backend["description"]
    assert backend["raw_data"]["board_token"] == BOARD_TOKEN
    assert backend["raw_data"]["payload"]["id"] == 91001


@requires_postgres
def test_greenhouse_sync_skips_malformed_jobs_without_aborting() -> None:
    good = greenhouse_job(91011, title="Senior Backend Engineer")
    also_good = greenhouse_job(91012, title="Junior Support Engineer", location="Austin, TX")
    malformed = {"id": 91013, "title": "Broken", "content": "<p>  </p>"}
    responses = {
        f"/v1/boards/{BOARD_TOKEN}": httpx.Response(200, json=board_payload("Helix Care")),
        f"/v1/boards/{BOARD_TOKEN}/jobs": httpx.Response(
            200,
            json={"jobs": [good, malformed, "not-an-object", also_good]},
        ),
    }
    gh_client = _client_for(responses)
    _override_greenhouse(gh_client)
    try:
        with TestClient(app) as test_client:
            response = test_client.post(f"/sources/greenhouse/{BOARD_TOKEN}/sync")
    finally:
        app.dependency_overrides.pop(get_greenhouse_client, None)
        gh_client.close()

    assert response.status_code == 200, response.text
    body = response.json()
    # fetched includes dict rows that survived list parsing (good, malformed, also_good)
    assert body["fetched"] == 3
    assert body["inserted"] + body["updated"] == 2
    assert body["skipped"] == 1
    assert body["errors"][0]["source_job_id"] == "91013"

    database = Database(get_settings())
    session = database.session_factory()
    try:
        repo = JobRepository(session)
        assert repo.get_by_source_identity("greenhouse", "91011") is not None
        assert repo.get_by_source_identity("greenhouse", "91012") is not None
        assert repo.get_by_source_identity("greenhouse", "91013") is None
    finally:
        session.close()
        database.dispose()
