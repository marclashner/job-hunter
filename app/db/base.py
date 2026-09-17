"""SQLAlchemy declarative base. Import models from `app.models` so metadata is complete."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
