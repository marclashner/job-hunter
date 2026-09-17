"""Liveness/readiness health endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.health import HealthResponse
from app.services.health import check_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    response: Response,
    session: Annotated[Session, Depends(get_db)],
) -> HealthResponse:
    result = check_health(session)
    if result.status != "ok":
        response.status_code = 503
    return result
