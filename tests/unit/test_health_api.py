"""HTTP health endpoint tests with dependency overrides (no live database)."""

from collections.abc import Generator

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.main import app


class _OkSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        return None


class _FailingSession:
    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise RuntimeError("connection refused")


def _override_ok() -> Generator[_OkSession, None, None]:
    yield _OkSession()


def _override_fail() -> Generator[_FailingSession, None, None]:
    yield _FailingSession()


def test_health_endpoint_ok() -> None:
    app.dependency_overrides[get_db] = _override_ok
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_endpoint_degraded() -> None:
    app.dependency_overrides[get_db] = _override_fail
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "disconnected"}
