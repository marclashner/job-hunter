"""ASGI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.router import api_router
from app.config import get_settings
from app.db import Database

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

OPENAPI_DESCRIPTION = """\
Ingest public Greenhouse and Lever listings, run deterministic hard filters, evaluate \
jobs with JobEvaluationAgent, and review results in the dashboard.

The review UI is served at `/`. Interactive docs are at `/docs` (Swagger UI) and `/redoc`. \
Human Approve/Review/Reject decisions do not submit applications.
"""

OPENAPI_TAGS = [
    {"name": "health", "description": "Process and database liveness."},
    {
        "name": "candidate",
        "description": (
            "Grounded candidate profile and evidence. Agents must not invent experience."
        ),
    },
    {"name": "jobs", "description": "Job listings, hard filters, and per-job evaluation."},
    {
        "name": "sources",
        "description": (
            "Pull public Greenhouse Job Board and Lever postings JSON APIs (no HTML scraping)."
        ),
    },
    {
        "name": "evaluation",
        "description": "In-process batch evaluation. Default mode is live_llm.",
    },
    {
        "name": "review",
        "description": "Dashboard queue and human decisions. Does not submit applications.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.database = Database(settings)
    try:
        yield
    finally:
        app.state.database.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Autonomous Job Search Agent",
        version=__version__,
        description=OPENAPI_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        debug=settings.debug,
    )
    application.include_router(api_router)
    if WEB_DIR.is_dir():
        application.mount("/web", StaticFiles(directory=WEB_DIR), name="web")

        @application.get("/", include_in_schema=False)
        def review_dashboard() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

    return application


app = create_app()
