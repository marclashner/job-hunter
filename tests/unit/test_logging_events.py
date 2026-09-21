"""Structured log payload tests."""

import json
import logging

import pytest

from app.logging_events import log_event


def test_log_event_emits_json_payload(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("tests.logging_events")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(logger, "evaluation.batch.started", discovered=3, dry_run=False)
    assert caplog.records
    payload = json.loads(caplog.records[0].getMessage())
    assert payload["event"] == "evaluation.batch.started"
    assert payload["discovered"] == 3
    assert payload["dry_run"] is False
