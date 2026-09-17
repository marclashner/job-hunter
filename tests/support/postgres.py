"""Helpers for live PostgreSQL tests."""

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.db import Database


def postgres_is_reachable() -> bool:
    database = Database(get_settings())
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        database.dispose()


requires_postgres = pytest.mark.skipif(
    not postgres_is_reachable(),
    reason="PostgreSQL is not reachable at DATABASE_URL",
)
