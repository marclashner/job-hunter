"""Live database connectivity tests."""

from sqlalchemy import text

from app.db import Database
from tests.support.postgres import requires_postgres


@requires_postgres
def test_database_executes_select_one(database: Database) -> None:
    with database.engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
