"""FastAPI dependency providers."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from app.db import Database


def get_db(request: Request) -> Generator[Session, None, None]:
    database: Database = request.app.state.database
    yield from database.session()
