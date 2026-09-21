"""Top-level API router."""

from fastapi import APIRouter

from app.api.candidate import router as candidate_router
from app.api.evaluation import router as evaluation_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.review import router as review_router
from app.api.sources import router as sources_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(candidate_router)
api_router.include_router(jobs_router)
api_router.include_router(evaluation_router)
api_router.include_router(review_router)
api_router.include_router(sources_router)
