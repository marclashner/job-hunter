"""Verify that the configured PostgreSQL database accepts connections."""

from __future__ import annotations

import sys

from sqlalchemy import text

from app.config import get_settings
from app.db import Database


def main() -> int:
    settings = get_settings()
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"database connection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        database.dispose()

    print(f"database connection ok: {settings.sqlalchemy_database_uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
