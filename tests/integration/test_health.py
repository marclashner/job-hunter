"""Live HTTP tests against the application and PostgreSQL."""

from fastapi.testclient import TestClient

from app.main import app
from tests.support.postgres import requires_postgres


@requires_postgres
def test_health_uses_live_database() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
