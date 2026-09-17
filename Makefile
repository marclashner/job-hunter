UV ?= uv
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

.PHONY: install sync test run lint fmt typecheck migrate migrate-new up down db-check

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

up:
	docker compose up -d

down:
	docker compose down

db-check:
	$(UV) run python scripts/check_db.py
