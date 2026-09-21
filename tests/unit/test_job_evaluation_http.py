"""Job evaluation HTTP tests with dependency overrides (no live model)."""

from collections.abc import Generator
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


def _session_without_job() -> Generator[MagicMock, None, None]:
    session = MagicMock()
    session.get.return_value = None
    yield session


def test_evaluate_job_not_found() -> None:
    app.dependency_overrides[get_db] = _session_without_job
    try:
        with TestClient(app) as client:
            response = client.post(f"/jobs/{uuid4()}/evaluate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}
