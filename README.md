# Autonomous Job Search Agent

Production-oriented scaffold for an AI job-search automation platform.

This repository currently provides the application shell: configuration, FastAPI, PostgreSQL, SQLAlchemy 2.x, Alembic, tests, and developer tooling. Job-search agents, sources, and scoring are not implemented yet.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 13+ (Docker Compose is the documented path; a local server also works)

## Quick start

```bash
cp .env.example .env
uv sync --group dev
docker compose up -d
make migrate
make run
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
make db-check
make test
```

A successful health response looks like:

```json
{"status":"ok","database":"connected"}
```

If the database is unreachable, the same endpoint returns HTTP 503 with `"status": "degraded"`.

## Candidate profile

Seed a placeholder senior engineer (replace `data/candidate/*.json` with real data):

```bash
make migrate
make seed
```

- `GET /candidate/profile` — grounded profile (`evidence_backed` | `derived` | `unknown`)
- `GET /candidate/evidence` — atomic claims agents may use

See [docs/candidate-evidence.md](docs/candidate-evidence.md).

## Jobs

- `POST /jobs`
- `GET /jobs` — filters: `source`, `title`, `location`, `remote_policy`, `seniority`, `minimum_salary`; pagination: `limit`, `offset`
- `GET /jobs/{id}`
- `POST /sources/greenhouse/{board_token}/sync` — Greenhouse Job Board JSON API (not HTML scraping). Upserts by `source` + `source_job_id`.

Duplicate `source` + `source_job_id` on `POST /jobs` returns HTTP 409. Sync uses upsert instead. Duplicate descriptions share a `content_hash` and set `is_duplicate_description`.

## Configuration

All runtime settings are environment variables (see `.env.example`). Secrets belong in `.env`, which is gitignored.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5433/jobsearch` |
| `APP_ENV` | Environment name (`development`, `test`, `production`) |
| `DEBUG` | FastAPI debug flag |
| `API_HOST` / `API_PORT` | Bind address used by operators; `make run` currently binds `0.0.0.0:8000` |

Docker Compose publishes Postgres on **host port 5433** so it does not collide with a local Postgres on 5432.

If you use a Homebrew/local Postgres instead of Compose, set `DATABASE_URL` accordingly, for example:

```text
DATABASE_URL=postgresql+psycopg://YOUR_USER@localhost:5432/jobsearch
```

## Developer commands

| Command | Action |
| --- | --- |
| `make install` | Install runtime and dev dependencies with uv |
| `make run` | Start the API with reload |
| `make test` | Run pytest |
| `make lint` | Ruff lint and format check |
| `make fmt` | Apply Ruff fixes |
| `make typecheck` | mypy on `app` |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Load/replace candidate JSON into Postgres |
| `make up` / `make down` | Start/stop Compose Postgres |
| `make db-check` | Ping the configured database |

## Layout

```text
app/            Application package (API, DB, config, future agents/sources/scoring)
alembic/        Schema migrations
tests/unit      Isolated tests (no live database required)
tests/integration  Tests that exercise Postgres and the HTTP app
scripts/        Operator utilities
docs/           Architecture notes
```

## Tests

```bash
uv run pytest
```

Integration tests skip automatically if PostgreSQL is not reachable at `DATABASE_URL`.
