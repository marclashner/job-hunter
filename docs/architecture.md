# Architecture

The initial scaffold is a modular FastAPI service with a PostgreSQL persistence layer. Job-search behavior is intentionally absent.

## Layers

- **`app/api`**: HTTP routers and FastAPI dependencies. Routers stay thin and delegate to services.
- **`app/services`**: Use-case logic (health, candidate profile/evidence, job ingestion).
- **`app/schemas`**: Pydantic v2 request/response models. These are not ORM models.
- **`app/models`**: SQLAlchemy ORM mappings (`CandidateProfile`, `CandidateEvidence`, `Job`).
- **`app/repositories`**: Query helpers used by services.
- **`app/db`**: Engine, session factory, and declarative base.
- **`app/config.py`**: `pydantic-settings` configuration. The process environment is the source of truth.
- **`app/agents`, `app/sources`, `app/scoring`**: `app/agents` holds `JobEvaluationAgent` (OpenAI Agents SDK). `app/sources` holds job-board adapters. `app/scoring` holds deterministic hard filters. See [agents.md](agents.md) and [scoring.md](scoring.md).

## Runtime wiring

`create_app()` constructs a FastAPI instance. The lifespan hook creates a `Database` (engine + sessionmaker) on `app.state` and disposes it on shutdown. Handlers receive a `Session` through `get_db`.

Alembic uses the same `Settings.database_url` as the application. Do not duplicate credentials in `alembic.ini`.

## Health

`GET /health` runs `SELECT 1` on PostgreSQL:

- `200` and `{"status":"ok","database":"connected"}` when the ping succeeds
- `503` and `{"status":"degraded","database":"disconnected"}` when it fails

## Candidate profile

`CandidateProfile` stores structured preferences and experience fields. `CandidateEvidence` stores atomic claims. `GET /candidate/profile` wraps each field in a `GroundedValue` (`evidence_backed`, `derived`, or `unknown`) so agents cannot treat missing information as fact. Details are in `docs/candidate-evidence.md`.

## Jobs

Ingested listings live in `jobs`. `source` + `source_job_id` is unique. `raw_data` keeps the original payload. `content_hash` is a SHA-256 of the normalized description so duplicate text is detectable across sources.

- `POST /jobs` — create (409 if the source identity already exists)
- `GET /jobs` — filter by source, title, location, remote_policy, seniority, minimum_salary; paginate with `limit`/`offset`
- `GET /jobs/{id}` — single listing
- `POST /sources/greenhouse/{board_token}/sync` — pull the public Greenhouse Job Board JSON API, normalize, and upsert. Malformed rows are skipped. Repeating the sync updates existing rows instead of duplicating them.
- `POST /sources/lever/{site}/sync` — same sync pipeline against Lever's public postings JSON API, including pagination.
- `POST /jobs/{id}/hard-filter` — deterministic eligibility vs the primary candidate. Missing salary/location/policy does not fail the job. See [scoring.md](scoring.md).
- `POST /jobs/{id}/evaluate` — `JobEvaluationAgent` by default (`evaluation_mode=live_llm`). Persists provenance (`evaluation_mode`, `model`, `provider`, `llm_request_id`, `fallback_reason`). Failed live calls error; they do not store an offline score as live. `offline_rubric` and `mock` only when requested.
- `POST /evaluation/batch` — in-process batch with the same `evaluation_mode` rules.

## Testing

Unit tests override FastAPI dependencies or call services with doubles. Integration tests use the real engine against PostgreSQL and skip when the database is down.
