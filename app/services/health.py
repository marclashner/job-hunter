"""Health-check application service."""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


def check_health(session: Session) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        return HealthResponse(status="degraded", database="disconnected")
    return HealthResponse(status="ok", database="connected")
