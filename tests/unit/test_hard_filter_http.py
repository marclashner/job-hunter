"""Hard-filter HTTP tests with dependency overrides (no live database)."""

from collections.abc import Generator
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app
from app.models.job import Job


def _session_without_job() -> Generator[MagicMock, None, None]:
    session = MagicMock()
    session.get.return_value = None
    yield session


def _session_with_job_without_profile() -> Generator[MagicMock, None, None]:
    session = MagicMock()
    session.get.return_value = MagicMock(spec=Job)
    session.scalars.return_value.one_or_none.return_value = None
    yield session


def test_hard_filter_job_not_found() -> None:
    app.dependency_overrides[get_db] = _session_without_job
    try:
        with TestClient(app) as client:
            response = client.post(f"/jobs/{uuid4()}/hard-filter")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_hard_filter_profile_not_found() -> None:
    app.dependency_overrides[get_db] = _session_with_job_without_profile
    try:
        with TestClient(app) as client:
            response = client.post(f"/jobs/{uuid4()}/hard-filter")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "Candidate profile not found" in response.json()["detail"]
