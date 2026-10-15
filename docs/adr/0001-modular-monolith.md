# 0001. Modular monolith with one database

Date: 2026-10-14
Status: accepted

## Context

The product has many distinct concerns (profile, personas, memory, retrieval, goals, safety, voice). Splitting them into services at the start would add deployment, networking and consistency problems before there is any load or any team boundary to justify them.

## Decision

One FastAPI application and one Postgres database, organised as modules under `apps/api/app/modules/`. A module exposes a service interface and keeps its tables private; other modules call the interface. A separate worker process runs background jobs from the same codebase. Vector search uses pgvector in the same database rather than a separate vector store.

## Consequences

Transactions span modules when they need to, and local development is one `docker compose up`. The cost is discipline: nothing but convention stops a module reaching into another's tables, so reviews must enforce it. If a module later needs independent scaling (retrieval is the likely first), its service interface is already the seam to cut along.
