"""ORM models. Import every model module here so Alembic sees complete metadata."""

from app.db.base import Base

__all__ = ["Base"]
