"""Batch evaluation HTTP validation without a live model."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app


def test_batch_evaluation_rejects_inverted_date_range() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/evaluation/batch",
            json={
                "discovered_after": datetime(2026, 9, 21, tzinfo=UTC).isoformat(),
                "discovered_before": datetime(2026, 9, 1, tzinfo=UTC).isoformat(),
            },
        )
    assert response.status_code == 422
