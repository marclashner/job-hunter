"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest

from app.config import get_settings


@pytest.fixture
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
