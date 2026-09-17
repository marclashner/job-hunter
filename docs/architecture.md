# Architecture

The initial scaffold is a modular FastAPI service with a PostgreSQL persistence layer. Job-search behavior is intentionally absent.

## Layers

- **`app/api`**: HTTP routers and FastAPI dependencies. Routers stay thin and delegate to services.
- **`app/services`**: Use-case logic. The only implemented service is health checking.
- **`app/schemas`**: Pydantic v2 request/response models. These are not ORM models.
- **`app/models`**: SQLAlchemy ORM mappings. Empty until domain tables exist.
- **`app/db`**: Engine, session factory, and declarative base.
- **`app/config.py`**: `pydantic-settings` configuration. The process environment is the source of truth.
- **`app/agents`, `app/sources`, `app/scoring`**: Reserved packages for later work.

## Runtime wiring

`create_app()` constructs a FastAPI instance. The lifespan hook creates a `Database` (engine + sessionmaker) on `app.state` and disposes it on shutdown. Handlers receive a `Session` through `get_db`.

Alembic uses the same `Settings.database_url` as the application. Do not duplicate credentials in `alembic.ini`.

## Health

`GET /health` runs `SELECT 1` on PostgreSQL:

- `200` and `{"status":"ok","database":"connected"}` when the ping succeeds
- `503` and `{"status":"degraded","database":"disconnected"}` when it fails

## Testing

Unit tests override FastAPI dependencies or call services with doubles. Integration tests use the real engine against PostgreSQL and skip when the database is down.
