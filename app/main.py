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
        title=settings.app_name,
        version=__version__,
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
