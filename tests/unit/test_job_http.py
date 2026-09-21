"""Job HTTP tests with dependency overrides (no live database)."""

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


def test_get_job_not_found() -> None:
    app.dependency_overrides[get_db] = _empty_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/jobs/{uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
