UV ?= uv
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

.PHONY: install sync test run lint fmt typecheck migrate migrate-new seed up down db-check openapi

install sync:
	$(UV) sync --group dev

test:
	$(UV) run pytest

run:
	$(UV) run uvicorn app.main:app --reload --host $(API_HOST) --port $(API_PORT)

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck:
	$(UV) run mypy app

migrate:
	$(UV) run alembic upgrade head

migrate-new:
	$(UV) run alembic revision --autogenerate -m "$(m)"

seed:
	$(UV) run python scripts/seed_candidate.py

up:
	docker compose up -d

down:
	docker compose down

db-check:
	$(UV) run python scripts/check_db.py

openapi:
	$(UV) run python scripts/export_openapi.py
