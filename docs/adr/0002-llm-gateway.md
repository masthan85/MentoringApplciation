# 0002. A provider-agnostic LLM gateway

Date: 2026-10-14
Status: accepted

## Context

The product must not be tied to one model vendor, and model names and prices change often. Different jobs need different models: small and cheap for classification, larger for the mentoring conversation.

## Decision

All model calls go through `app/modules/llm_gateway`. Callers name a route; `routes.yaml` maps each route to an ordered list of provider and model targets, with a token limit, timeout and retry count. The gateway:

- retries transient failures with backoff, then falls back to the next target;
- does not retry or fall back on invalid requests, which would fail everywhere;
- skips targets whose provider has no credentials configured;
- switches to the mock provider for every route when `LLM_DEFAULT_PROVIDER=mock`;
- logs one structured line per call with tokens, latency and cost, and warns when one call is expensive;
- turns the vendor SDKs' own retries off so there is one retry policy, not two.

Requests carry no sampling parameters (temperature and similar). Current models reject some of them, and prompts should not depend on them. Reasoning effort is set per target in configuration.

Streaming retries and fallback apply only until the first token has reached the caller. After that a failure is raised, because restarting would show the user two different answers.

## Consequences

Switching or adding a vendor is a new adapter plus a routes change. Costs are only known for models listed under `pricing:` and are logged as null otherwise. Model identifiers in `routes.yaml`, especially the OpenAI fallbacks, must be confirmed against provider documentation before production use.
