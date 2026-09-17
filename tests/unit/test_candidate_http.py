"""Candidate HTTP tests with dependency overrides (no live database)."""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


def _missing_profile_session() -> Generator[MagicMock, None, None]:
    session = MagicMock()
    session.scalars.return_value.one_or_none.return_value = None
    yield session


def test_profile_not_found() -> None:
    app.dependency_overrides[get_db] = _missing_profile_session
    try:
        with TestClient(app) as client:
            response = client.get("/candidate/profile")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_evidence_not_found() -> None:
    app.dependency_overrides[get_db] = _missing_profile_session
    try:
        with TestClient(app) as client:
            response = client.get("/candidate/evidence")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
