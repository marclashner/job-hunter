"""Live candidate profile and evidence HTTP tests."""

from fastapi.testclient import TestClient

from app.db import Database
from app.main import app
from app.services.candidate import replace_from_seed
from app.services.candidate_seed import load_seed_bundle
from tests.support.postgres import requires_postgres


@requires_postgres
def test_candidate_endpoints_return_grounded_seed_data(database: Database) -> None:
    bundle = load_seed_bundle()
    session = database.session_factory()
    try:
        replace_from_seed(session, bundle)
        session.commit()
    finally:
        session.close()

    with TestClient(app) as client:
        profile_response = client.get("/candidate/profile")
        evidence_response = client.get("/candidate/evidence")
        filtered = client.get("/candidate/evidence", params={"category": "frontend"})

    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["key"] == bundle.profile.key
    assert profile["name"]["provenance"] == "evidence_backed"
    assert profile["name"]["value"] == bundle.profile.name
    assert profile["summary"]["provenance"] == "derived"
    assert profile["summary"]["interpretation_notes"]
    assert profile["ai_experience"]["provenance"] == "evidence_backed"
    assert isinstance(profile["unknown_categories"], list)
    assert "Never invent candidate experience" in profile["agent_usage_rule"]

    assert evidence_response.status_code == 200
    payload = evidence_response.json()
    keys = {item["key"] for item in payload["items"]}
    assert {item.key for item in bundle.evidence} <= keys
    assert filtered.status_code == 200
    assert filtered.json()["items"] == []
