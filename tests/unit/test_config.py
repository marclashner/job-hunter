"""Configuration tests."""

import pytest

from app.config import get_settings


def test_database_url_from_environment(
    clear_settings_cache: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://tester:secret@db.example:5432/jobsearch",
    )
    settings = get_settings()
    assert "tester" in settings.sqlalchemy_database_uri
    assert settings.sqlalchemy_database_uri.endswith("/jobsearch")


def test_pool_settings_have_defaults(clear_settings_cache: None) -> None:
    settings = get_settings()
    assert settings.database_pool_size >= 1
    assert settings.database_max_overflow >= 0
