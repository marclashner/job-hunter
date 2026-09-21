"""Committed OpenAPI spec must match the running application."""

import json
from pathlib import Path

from app import __version__
from app.main import app

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def test_exported_openapi_matches_application() -> None:
    generated = app.openapi()
    exported = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    assert exported["info"]["version"] == __version__
    assert generated["info"]["version"] == __version__
    assert generated["info"]["title"] == "Autonomous Job Search Agent"
    assert exported == generated


def test_openapi_includes_review_and_source_paths() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    paths = spec["paths"]
    assert "/sources/greenhouse/{board_token}/sync" in paths
    assert "/sources/lever/{site}/sync" in paths
    assert "/evaluation/batch" in paths
    assert "/review/summary" in paths
    assert "/review/jobs" in paths
    assert "/review/jobs/{job_id}/decision" in paths
