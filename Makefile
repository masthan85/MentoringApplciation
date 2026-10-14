.PHONY: setup db api worker web test e2e lint format openapi up down

setup:           ## Install Python and web dependencies
	uv sync --all-packages --python 3.12
	npm --prefix apps/web ci

db:              ## Create roles/databases on a local Postgres and run migrations
	psql -f infra/postgres/01-roles.sql
	bash infra/postgres/02-databases.sh
	cd apps/api && uv run alembic upgrade head

api:             ## Run the API with reload
	cd apps/api && uv run uvicorn app.main:create_app --factory --reload

worker:          ## Run the background worker
	cd apps/worker && uv run arq worker.main.WorkerSettings

web:             ## Run the web app
	npm --prefix apps/web run dev

test:            ## Run all Python tests (needs Postgres and the roles from `make db`)
	cd apps/api && uv run pytest -q
	cd apps/worker && uv run pytest -q

e2e:             ## Browser tests (needs Postgres, Redis and `make db`)
	npm --prefix apps/web run test:e2e

lint:            ## Lint and type-check everything
	uv run ruff check .
	uv run ruff format --check .
	cd apps/api && uv run mypy
	cd apps/worker && uv run mypy
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck

format:
	uv run ruff check . --fix
	uv run ruff format .

openapi:         ## Regenerate the OpenAPI document and the typed web client
	cd apps/api && uv run python scripts/export_openapi.py
	npm --prefix apps/web run gen:api

up:              ## Start the whole stack in Docker
	docker compose -f infra/docker-compose.yml up --build

down:
	docker compose -f infra/docker-compose.yml down
