"""Live PostgreSQL fixtures."""

from collections.abc import Iterator

import pytest

from app.config import get_settings
from app.db import Database


@pytest.fixture
def database() -> Iterator[Database]:
    db = Database(get_settings())
    try:
        yield db
    finally:
        db.dispose()
