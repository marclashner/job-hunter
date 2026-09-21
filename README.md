# Autonomous Job Search Agent

Production-oriented scaffold for an AI job-search automation platform.

This repository currently provides configuration, FastAPI, PostgreSQL, SQLAlchemy 2.x, Alembic, candidate evidence, job ingestion (including Greenhouse and Lever), deterministic hard filters, and `JobEvaluationAgent` (OpenAI Agents SDK). Application-writing agents are not implemented.

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

Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI) and `/redoc`. The committed spec is [docs/openapi.json](docs/openapi.json) (regenerate with `make openapi`).

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
- `POST /sources/lever/{site}/sync` — Lever postings JSON API. Same upsert rules.
- `POST /jobs/{id}/hard-filter` — deterministic knock-out rules vs the primary candidate. Unlisted salary does not reject the job (`salary_unknown: true`). See [docs/scoring.md](docs/scoring.md).
- `POST /jobs/{id}/evaluate` — default `evaluation_mode=live_llm`. Provenance fields distinguish live, `offline_rubric`, and `mock`. Failed live calls error instead of storing an offline score as live. See [docs/agents.md](docs/agents.md).
- `POST /evaluation/batch` — evaluate many unevaluated jobs in-process (hard filters, then agent). Optional `source`, date range, `limit`, `dry_run`, `reevaluate`, `concurrency`.
- Review UI at `/` — dashboard, job queue, and detail. Human Approve/Review/Reject only; applications are not submitted.

Duplicate `source` + `source_job_id` on `POST /jobs` returns HTTP 409. Sync uses upsert instead. Duplicate descriptions share a `content_hash` and set `is_duplicate_description`.

## Live jobs on the dashboard

Use this path when you want **real Greenhouse/Lever listings**, **live LLM scores**, and results in the review UI. Do it after the candidate profile is seeded (`make seed`) and Postgres is migrated. Live evaluation calls OpenAI and costs money; keep `EVALUATION_RATE_LIMIT_PER_MINUTE` in mind.

1. Put `OPENAI_API_KEY` in `.env`. Leave `OPENAI_MODEL` at `gpt-4o-mini` unless you intend to change it.
2. Start the API (`make run`). The dashboard is [http://127.0.0.1:8000/](http://127.0.0.1:8000/).
3. Find public board slugs from the careers URL (not from HTML scraping):
   - Greenhouse: `https://boards.greenhouse.io/{board_token}`
   - Lever: `https://jobs.lever.co/{site}`
4. Pull listings. Repeating a sync **upserts**; it does not duplicate `source` + `source_job_id`.

```bash
curl -sS -X POST "http://127.0.0.1:8000/sources/greenhouse/BOARD_TOKEN/sync"
curl -sS -X POST "http://127.0.0.1:8000/sources/lever/SITE/sync"
```

A 404 means that public board does not exist. The JSON body reports `fetched`, `inserted`, `updated`, `skipped`, and per-row `errors`.

5. Optional: count hard-filter discards without calling the model.

```bash
curl -sS -X POST http://127.0.0.1:8000/evaluation/batch \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true, "limit": 50}'
```

6. Evaluate unevaluated jobs with the live agent (default `evaluation_mode` is `live_llm`). Filter to a source if you only synced one board. Start with a small `limit`.

```bash
curl -sS -X POST http://127.0.0.1:8000/evaluation/batch \
  -H "Content-Type: application/json" \
  -d '{"source": "greenhouse", "limit": 20}'
```

A failed live call is an error (HTTP 502 on a single job; batch `errors` entries). It does **not** store an offline score as live. Pass `"evaluation_mode": "offline_rubric"` or `"mock"` only when you explicitly want those modes. Already-evaluated jobs are skipped unless `"reevaluate": true`.

7. Refresh [http://127.0.0.1:8000/](http://127.0.0.1:8000/). The queue shows evaluated jobs. Filter by source (`greenhouse` / `lever`), recommendation, minimum score, remote, or date discovered. Open a row for description, evaluation, cited evidence, hard filters, and the application URL. Approve / Review / Reject are human decisions only.

Sync again whenever you want newer postings; then run another batch so the dashboard picks up scores for the new rows.

## Configuration

All runtime settings are environment variables (see `.env.example`). Secrets belong in `.env`, which is gitignored.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `postgresql+psycopg://user:pass@host:5433/jobsearch` |
| `APP_ENV` | Environment name (`development`, `test`, `production`) |
| `DEBUG` | FastAPI debug flag |
| `API_HOST` / `API_PORT` | Bind address used by operators; `make run` currently binds `0.0.0.0:8000` |
| `OPENAI_API_KEY` | OpenAI key for JobEvaluationAgent (optional until you call `/jobs/{id}/evaluate` or `/evaluation/batch`) |
| `OPENAI_MODEL` | Agents SDK model id (default `gpt-4o-mini`) |
| `EVALUATION_CONCURRENCY` | Batch worker threads (default `2`) |
| `EVALUATION_RATE_LIMIT_PER_MINUTE` | Max model calls per minute in a batch (default `30`) |

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
| `make openapi` | Write `docs/openapi.json` from the current FastAPI app |

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
