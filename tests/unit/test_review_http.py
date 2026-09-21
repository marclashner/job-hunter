"""Review dashboard HTTP tests (no database)."""

from collections.abc import Generator
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


def _empty_session() -> Generator[MagicMock, None, None]:
    session = MagicMock()
    session.get.return_value = None
    yield session


def test_review_job_not_found() -> None:
    app.dependency_overrides[get_db] = _empty_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/review/jobs/{uuid4()}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_dashboard_html_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Job review" in response.text
