# Mentor

An adaptive AI mentor for data, AI and software professionals in the UK. It learns your role, goals and commitments, mentors from the right professional perspective, keeps a record you can see, edit and delete, and works alongside human mentors rather than pretending to replace them.

The product definition is `docs/BUILD_SPEC.md`, and the build follows it phase by phase. The market research behind it is in `reports/`.

## Status

Phases 0 (foundations) and 1 (core mentoring loop) are built. Knowledge, voice and the Mentor Encyclopedia are Phase 2.

| Area | State |
|---|---|
| API skeleton (FastAPI, health checks, problem-detail errors, request logging) | Done |
| Postgres with migrations, pgvector, row-level security | Done |
| Auth: OIDC/JWKS verification (Auth0, Clerk, Entra) plus a local dev mode | Done |
| LLM gateway: Anthropic, OpenAI and mock providers, routing, retries, fallback, cost logging | Done |
| Worker (Arq) with a smoke job | Done |
| Web app (Next.js) with a status page and a typed API client | Done |
| Docker Compose, CI, ADRs | Done |
| Profile, onboarding conversation, editable profile card | Done |
| Mentor packs (3 packs, 7 lenses) and persona selection | Done, content needs expert review |
| Turn pipeline with streaming, routing, safety rules, fixed crisis and refusal replies | Done, crisis wording is a draft |
| Typed memory with extraction, review page, export and delete; consent-gated encrypted sensitive items | Done |
| Chat, onboarding and notes screens | Done |
| Encyclopedia, retrieval, Natural Voice, Writing Fingerprint (Phase 2) | Not started |

## Run it

You need Docker, or Python 3.12 with uv, Node 22, Postgres 16 with pgvector and Redis 7.

With Docker:

    docker compose -f infra/docker-compose.yml up --build

The web app is on http://localhost:3000, the API on http://localhost:8000 (interactive docs at `/docs`). With no API keys set, every model call is answered by the mock provider.

Without Docker:

    make setup
    make db        # creates roles and databases, runs migrations (needs psql access)
    make api       # terminal 1
    make worker    # terminal 2
    make web       # terminal 3

Copy `.env.example` to `.env` to change settings. To call a real model, set `LLM_DEFAULT_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.

## Checks

    make test      # Python tests (API and worker)
    make lint      # ruff, mypy (strict), eslint, tsc
    make e2e       # Playwright, against a real browser, the API and the web build

The API tests run against a real Postgres, as the same non-owner role the app uses at runtime, because the row-level security rules are part of what is being tested.

## Layout

    apps/api        FastAPI app, one module per area under app/modules
    apps/worker     background jobs (Arq)
    apps/web        Next.js frontend
    packs/          mentor pack definitions (Phase 1)
    content/        Mentor Encyclopedia sources (Phase 2)
    evals/          regression scenarios and rubrics (Phase 3 runner)
    infra/          Docker Compose, Dockerfiles, database setup scripts
    docs/           architecture decision records, schema notes, OpenAPI document
    reports/        competitive research

Modules talk to each other through their service interfaces and never read another module's tables.

## Working with models

Application code never names a model. It asks the gateway for a route (`classifier`, `chat_small`, `chat_large`, `rewrite_small`, `judge`, `embedding`) and `apps/api/app/modules/llm_gateway/routes.yaml` decides which provider and model serve it, in what fallback order, and at what price. Change that file, not the code, to change models.

## Decisions

See `docs/adr/`. Start with the modular monolith, the gateway, and the database roles, because they explain the shape of everything else.
