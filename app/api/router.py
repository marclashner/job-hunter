"""Top-level API router."""

from fastapi import APIRouter

from app.api.candidate import router as candidate_router
from app.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(candidate_router)
