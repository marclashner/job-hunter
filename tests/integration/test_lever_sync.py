"""Lever sync against mocked HTTP and live PostgreSQL."""

from collections.abc import Iterator
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.api.sources import get_lever_client
from app.config import get_settings
from app.db import Database
from app.main import app
from app.models.enums import JobSource
from app.repositories.jobs import JobRepository
from app.sources.lever import LeverClient
from tests.support.lever import SITE, lever_client, lever_posting
from tests.support.postgres import requires_postgres


def _client_for(responses: dict[str, httpx.Response | list[httpx.Response]]) -> LeverClient:
    return LeverClient(
        lever_client(responses),
        sleep=lambda _delay: None,
        max_retries=1,
    )


def _override_lever(client: LeverClient) -> None:
    def dependency() -> Iterator[LeverClient]:
        yield client

    app.dependency_overrides[get_lever_client] = dependency


@requires_postgres
def test_lever_sync_fetches_normalizes_inserts_and_is_idempotent() -> None:
    id_one = f"lev-{uuid4().hex}"
    id_two = f"lev-{uuid4().hex}"
    job_one = lever_posting(id_one, title="Senior Backend Engineer")
    job_two = lever_posting(
        id_two,
        title="Staff Platform Engineer",
        location="New York, NY",
        workplace="hybrid",
        description_plain="Own Kubernetes platforms and observability.",
    )
    responses = {
        f"/v0/postings/{SITE}": httpx.Response(200, json=[job_one, job_two]),
    }
    client = _client_for(responses)
    _override_lever(client)
    try:
        with TestClient(app) as test_client:
            first = test_client.post(f"/sources/lever/{SITE}/sync")
            second = test_client.post(f"/sources/lever/{SITE}/sync")
            listing = test_client.get("/jobs", params={"source": "lever", "limit": 100})
    finally:
        app.dependency_overrides.pop(get_lever_client, None)
        client.close()

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["source"] == JobSource.LEVER.value
    assert body["company_identifier"] == SITE
    assert body["fetched"] == 2
    assert body["inserted"] == 2
    assert body["updated"] == 0
    assert body["skipped"] == 0

    assert second.status_code == 200
    again = second.json()
    assert again["fetched"] == 2
    assert again["inserted"] == 0
    assert again["updated"] == 2

    items = [item for item in listing.json()["items"] if item["source_job_id"] in {id_one, id_two}]
    assert len(items) == 2
    backend = next(item for item in items if item["source_job_id"] == id_one)
    assert backend["company"] == SITE
    assert backend["source"] == "lever"
    assert "Build Python APIs" in backend["description"]
    assert "<p>" not in backend["description"]
    assert backend["raw_data"]["site"] == SITE
    assert backend["raw_data"]["payload"]["id"] == id_one


@requires_postgres
def test_lever_sync_skips_malformed_jobs_without_aborting() -> None:
    id_good = f"lev-{uuid4().hex}"
    id_also = f"lev-{uuid4().hex}"
    id_bad = f"lev-{uuid4().hex}"
    good = lever_posting(id_good, title="Senior Backend Engineer")
    also_good = lever_posting(
        id_also,
        title="Junior Support Engineer",
        location="Austin, TX",
        workplace="on-site",
    )
    malformed = {"id": id_bad, "text": "Broken", "description": "<p>  </p>"}
    responses = {
        f"/v0/postings/{SITE}": httpx.Response(
            200, json=[good, malformed, "not-an-object", also_good]
        ),
    }
    client = _client_for(responses)
    _override_lever(client)
    try:
        with TestClient(app) as test_client:
            response = test_client.post(f"/sources/lever/{SITE}/sync")
    finally:
        app.dependency_overrides.pop(get_lever_client, None)
        client.close()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["fetched"] == 3
    assert body["inserted"] + body["updated"] == 2
    assert body["skipped"] == 1
    assert body["errors"][0]["source_job_id"] == id_bad

    database = Database(get_settings())
    session = database.session_factory()
    try:
        repo = JobRepository(session)
        assert repo.get_by_source_identity("lever", id_good) is not None
        assert repo.get_by_source_identity("lever", id_also) is not None
        assert repo.get_by_source_identity("lever", id_bad) is None
    finally:
        session.close()
        database.dispose()
