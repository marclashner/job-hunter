"""Engine and session factory. Connections are opened lazily on first use."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def create_engine_from_settings(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_database_uri,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        future=True,
    )


class Database:
    """Process-scoped engine and session factory, typically stored on `app.state`."""

    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine_from_settings(settings)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            class_=Session,
        )

    def session(self) -> Generator[Session, None, None]:
        db_session = self.session_factory()
        try:
            yield db_session
        finally:
            db_session.close()

    def dispose(self) -> None:
        self.engine.dispose()
