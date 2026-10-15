# 0005. Tooling choices

Date: 2026-10-14
Status: accepted

## Context

A few tool choices affect how the repository is set up and are easy to get wrong.

## Decision

- **uv workspace** for Python, with one lockfile for `apps/api` and `apps/worker`. Python 3.12.
- **App factory.** `uvicorn app.main:create_app --factory`. There is no module-level `app`, so importing the package never needs production settings.
- **Alembic reads `MIGRATION_DATABASE_URL` directly**, not the application settings, so a migration job does not need auth or model keys.
- **Arq** for background jobs. It is small, async and fits our Redis. We will move to Celery only if we need features Arq lacks.
- **TypeScript is pinned to 5.9.** TypeScript 7 is current, but typescript-eslint and openapi-typescript do not support it yet. Revisit when they do.
- **Typed web client** is generated from the API's OpenAPI document (`docs/api/openapi.json`), and CI fails if either generated file is stale.

## Consequences

`make openapi` must be run after API changes. Docker images share one Python image for API, migrations and worker.
