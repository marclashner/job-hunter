"""JSON structured log lines for operators and log aggregators."""

from __future__ import annotations

import json
import logging
from typing import Any


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info("%s", json.dumps(payload, default=str, sort_keys=True))


def log_exception(logger: logging.Logger, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.exception("%s", json.dumps(payload, default=str, sort_keys=True))
