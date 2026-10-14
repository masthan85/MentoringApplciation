# Build specification: Adaptive AI Mentoring Platform (MVP)

You are the senior full-stack engineer and AI engineer building the MVP of an AI mentoring platform for data, AI and software professionals in the UK. Read this whole document before writing any code. It is the source of truth. If something here is unclear or seems wrong, stop and ask rather than guessing.

## 1. What we are building

A web app where a professional gets an AI mentor that:

- understands their role, seniority, stack and goals, and mentors from the right professional perspective (for example a senior data architect's view for a data engineer);
- remembers goals, decisions and commitments over months, in a structured record the user can see, edit, export and delete;
- runs a mentoring rhythm: goals, commitments, weekly check-ins, quarterly reviews with measurable progress;
- answers domain questions using a curated, cited knowledge base (the Mentor Encyclopedia);
- helps the user draft professional communication (Slack, email, executive summary, ADR, LinkedIn post) in their own natural voice;
- lets the user invite a human mentor and share an approved pre-session brief.

Positioning: specialist and hybrid. The AI makes human mentoring work better between sessions; it does not pretend to be human.

Initial audience: data engineers, data architects, analytics engineers, ML/AI engineers, software engineers, tech leads and first-time technology managers. Adults only. UK first.

## 2. Non-negotiable principles

1. **Simplicity first.** Modular monolith, one backend, one database. No microservices, no Kubernetes, no separate vector database at MVP.
2. **Deterministic where possible.** Use plain code for scheduling, goal state, permissions, routing, token budgets, scoring and lint metrics. Use small models for classification and extraction. Use a large model only for the mentoring conversation and long drafts. No open-ended agent loops.
3. **Provider-agnostic AI.** All model calls go through one internal LLM gateway module. Support at least two providers (Anthropic and OpenAI) behind one interface, configurable per route.
4. **The AI never claims to be human.** It never claims qualifications, licences, employment history or personal experience. Personas are perspectives, not biographies.
5. **Natural Voice, not detector evasion.** The writing-quality feature exists to remove mechanical LLM habits and improve clarity. Never build, test or market it for evading AI detectors. Never add deliberate errors.
6. **Accuracy beats style.** Any rewrite must preserve facts, numbers, names, versions, dates and code exactly. If preservation cannot be verified, ship the original.
7. **Privacy by design.** UK GDPR. User owns their data. Sensitive memories off by default.
8. **Tests and evaluation from day one.** Every module has unit tests. Prompt and persona changes are gated by an evaluation suite.

## 3. Technology stack

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic.
- Database: PostgreSQL 16 with pgvector, row-level security enabled. Full-text search (tsvector) for BM25-style retrieval.
- Cache and rate limiting: Redis.
- Background jobs: Arq (or Celery if you have a strong reason; explain it).
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS, responsive and mobile-first (PWA-ready).
- Auth: pluggable. Implement with an external provider (Auth0 or Clerk) via JWT verification; keep the provider swappable for Microsoft Entra External ID later. MFA supported by the provider.
- Payments: Stripe (subscriptions), behind a feature flag until Phase 4.
- LLM access: internal gateway module (a thin wrapper; LiteLLM is acceptable underneath). Embeddings via provider API, model name configurable.
- Re-ranking: a cross-encoder (sentence-transformers) running in the worker, behind an interface so it can be swapped for an API.
- Observability: structured JSON logs, OpenTelemetry traces, Langfuse (self-hostable) for LLM traces.
- Local dev: Docker Compose (api, worker, web, postgres, redis). Deployment target later is Azure UK South (Container Apps + Azure Database for PostgreSQL + Key Vault); write Bicep or Terraform only in Phase 4.
- CI: GitHub Actions running lint (ruff, mypy, eslint), tests and the evaluation smoke suite.

## 4. Repository layout

```
/apps/api            FastAPI app
  /app/modules/
    identity/        users, auth, consent, data-subject rights
    profile/         professional profile
    persona/         mentor lenses, selection, overrides
    orchestration/   per-turn pipeline
    llm_gateway/     providers, routing, retries, cost tracking
    voice/           style guidance, lint, targeted rewrite, preservation check
    fingerprint/     writing samples, stylometric features, voice card
    encyclopedia/    sources, ingestion, chunking, retrieval, citations
    memory/          typed memories, extraction, retrieval
    goals/           goals, milestones, commitments, check-ins, reviews
    studio/          drafting for channels, practice sessions
    mentors/         human mentor relationships, briefs, session notes
    safety/          risk classification, policies, output checks
    evaluation/      metrics, regression runner, feedback
    audit/           audit events
    notifications/   email reminders (in-app first)
  /app/core/         config, db, security, logging, errors
  /tests
/apps/worker         background jobs (memory extraction, ingestion, check-in scheduling, evals)
/apps/web            Next.js frontend
/packs               mentor pack definitions (YAML), version-controlled
/content             encyclopedia source content and manifests
/evals               regression scenarios and rubrics
/infra               docker-compose now; IaC later
/docs                architecture decision records (ADRs), API docs
```

Modules talk to each other through explicit service interfaces, never by reaching into another module's tables.

## 5. Mentor Packs and the Persona Engine

A persona is configuration, not a character. Build three packs for the MVP:

1. Data engineering and data architecture
2. AI/ML and GenAI engineering
3. Engineering leadership and career development

Each pack is a YAML file under `/packs` with a schema validated at startup. Each pack contains one or more **lenses**. A lens defines:

- `id`, `name`, `version`, `domain`
- `perspective`: one paragraph describing the viewpoint, written in the third person (e.g. "the perspective of an experienced data architect"), never as a biography
- `priorities`: ordered list (e.g. governance, lineage, total cost of ownership, operability)
- `questions_to_ask`: the questions this perspective typically raises
- `common_failure_modes`
- `vocabulary` and `terms_to_explain_for_juniors`
- `red_flags` to call out
- `depth_by_seniority`: guidance for junior / mid / senior / lead / executive
- `out_of_scope`: topics this lens must redirect

Selection logic:

1. Default lens chosen deterministically from profile (role + seniority) via a mapping table.
2. The per-turn classifier may suggest a different lens for this message (e.g. a security question). Switch only above a confidence threshold, and show the user which lens is active.
3. The user can pin a lens, combine up to two lenses (priorities merged by weight), or override completely. User choice always wins, except over safety.

Persona assembly produces a short system-prompt section from the lens plus the user's seniority. It must change the substance of answers (priorities, trade-offs, questions), not just the tone. The evaluation suite checks this by comparing answers to the same question under different lenses.

Hard rule enforced in the prompt and by an output check: no first-person claims of experience, employment, qualifications or credentials ("when I worked at…", "as a certified…").

## 6. Per-turn orchestration (keep it to four stages)

**Stage 1: parallel pre-processing (target under 300 ms excluding retrieval).**
- Deterministic rules (crisis keywords, prohibited-use patterns, channel detection from UI context).
- One small-model call with structured JSON output: `intent` (mentoring, technical_question, decision, drafting, practice, check_in, small_talk, other), `domain`, `risk_class` (normal, adjacent_regulated, crisis, prohibited), `suggested_lens`, `needs_retrieval` (bool), `time_sensitive` (bool).
- Concurrently load: profile, active persona, active goals, open commitments, top memories.
- If `needs_retrieval`, run encyclopedia retrieval.

**Stage 2: context assembly and routing (deterministic).**
- Build the prompt from templates in this order: safety policy, persona section, voice card, user profile summary, goals and open commitments, relevant memories, retrieved sources with IDs, recent conversation (rolling summary + last N turns).
- Enforce a token budget per section.
- Route by rules: crisis → fixed reviewed response, no model; prohibited → refusal template with an alternative; check_in and short replies → small model; mentoring, decisions, drafting → large model.

**Stage 3: single streamed generation.** Stream tokens to the client over Server-Sent Events. Require inline citation markers like `[S1]` for any claim drawn from retrieved sources.

**Stage 4: post-processing.**
- Always: deterministic voice lint (section 7) and safety output checks (no human-identity claims, no fabricated credentials, citations reference real source IDs).
- Drafting (Studio) or lint failure: targeted rewrite + preservation check (section 7). In live chat, do not block the stream; log lint scores and feed them into the next turn's guidance.
- Time-sensitive or high-risk answers: add an "as of [date]" note and a source check.
- Async after response: memory extraction, analytics, evaluation logging.

Store a `persona_snapshot`, model, token counts, latency, cost and lint scores on every assistant message.

## 7. Natural Voice (writing-quality engine)

Three layers.

**A. In-generation guidance.** A compact voice card in the prompt containing:
- channel norms (chat, Slack/Teams, email, executive summary, ADR/design note, LinkedIn post, spoken interview answer);
- mode: Natural Professional (default), Professional, Executive, Conversational, Technical, Academic, Concise, Detailed, My Style;
- the user's fingerprint summary (section 8);
- mentor voice principles: answer first; do not restate the question; prose by default; lists and headings only when content is genuinely list-shaped or the channel expects them; no generic openers ("Great question", "Certainly") or closers that repeat the body; no empty intensifiers; explain only what this user doesn't already know; British English unless the user writes American English;
- two or three approved exemplars from the user for this channel, if available.

**B. Deterministic lint.** Pure Python, runs in milliseconds, returns a score per signal and an overall pass/fail with thresholds per mode and channel. Signals:
- discourse-marker density per 100 words (furthermore, moreover, additionally, in conclusion, it is important to note, etc.), weighted by context, not a blacklist;
- sentence-length coefficient of variation compared with the user's baseline;
- heading and bullet ratio compared with channel expectations;
- formulaic opener and closer patterns;
- question restatement (embedding similarity between the first sentence and the user's message above a threshold);
- redundant conclusion (similarity between final paragraph and the rest);
- empty-adjective density (robust, seamless, comprehensive, cutting-edge, powerful, innovative) with domain exceptions (e.g. "robust standard errors");
- repeated n-grams and repeated sentence openings;
- length against channel target.

Make thresholds configurable in one file. Write thorough unit tests with good and bad examples.

**C. Targeted rewrite with preservation check.** Only when lint fails or for Studio drafts:
1. A small model rewrites only the flagged spans, instructed to keep every claim.
2. Preservation check: extract numbers, named entities, versions, dates, URLs and code blocks deterministically from before and after; they must match. Then run a claim-level entailment check (small NLI model or small LLM judge returning structured output).
3. If any check fails, return the original draft and log the failure.

Never apply rewriting to safety, crisis or refusal text. Never insert errors. Never offer an "undetectable" option.

## 8. Writing Fingerprint

- Users add writing samples they confirm are their own, tagged by channel. Never fingerprint text the user says someone else wrote.
- Edits the user makes to Studio drafts are captured (with consent) as additional signal.
- Compute a stylometric feature vector per channel: mean and spread of sentence length, paragraph length, vocabulary diversity (MTLD), contraction rate, British vs American spelling ratio, passive-voice rate, hedging rate, technical-term rate, first-person usage, question frequency, list usage, formality score.
- Generate a short natural-language voice card from the features (template-driven, optionally polished by a small model).
- Store exemplars for few-shot retrieval.
- Similarity metric: stylometric distance between output and user corpus, logged per draft.
- Users can view, edit and delete the fingerprint as a unit. No per-user fine-tuning.

## 9. Mentor Encyclopedia and retrieval

- Content lives in `/content` with a manifest per source. Only ingest content we are licensed to use: our own authored playbooks, open standards and public guidance (NIST AI RMF, OWASP, ICO guidance, UK government standards), and vendor documentation whose terms allow it. Do not ingest copyrighted books or paid bodies of knowledge.
- Metadata per chunk: domain, subtopic, source title, URL, authority tier (official, standard, peer_reviewed, expert_authored, community), published date, last reviewed date, volatility (stable, moderate, volatile), jurisdiction, licence, reviewer.
- Ingestion job: parse (Markdown, HTML, PDF), clean, sanitise for prompt injection, chunk by heading with overlap, embed, store.
- Retrieval: hybrid (Postgres full-text + pgvector), metadata filtering by domain and lens, top 30 → cross-encoder re-rank → top 5–8, with an authority boost and a freshness decay that depends on volatility.
- Retrieved text is wrapped as clearly delimited data, never instructions.
- Citations: the API returns sources with each answer; the UI shows them inline.
- Seed the MVP with a small starter set (I will supply content). Build an admin page to add, review and retire sources.

## 10. Memory

Typed records in Postgres, not an opaque vector dump.

- Working context: rolling conversation summary plus last N turns.
- Professional profile: structured fields.
- Long-term memories: `type` in (goal_context, decision, commitment, achievement, preference, improvement_area, project, advice_given), `content`, `source_message_id`, `confidence`, `sensitivity` (normal, sensitive), `created_at`, `last_confirmed_at`, `expires_at`, embedding.
- Sensitive memories (health, family circumstances, anything that looks like special category data) are not stored unless the user has opted in, and are then encrypted with a separate key and never shared with human mentors.

Extraction: after each conversation turn, a worker job asks a small model for memory candidates in a strict JSON schema. Normal items are saved and surfaced to the user as a small "Noted: …" chip with undo. Sensitive candidates require explicit confirmation. Deduplicate by embedding similarity and update rather than duplicate.

Retrieval: always include active goals and open commitments; then rank other memories by type relevance, recency and similarity within a token budget.

"My mentor's notes" page: list, edit, delete, export (JSON and Markdown) every memory, the profile and the fingerprint.

## 11. Goals, commitments and outcomes

- Goals with Goal Attainment Scaling levels (-2 to +2) defined at creation with the user's help, a baseline, target date and status.
- Milestones and commitments with due dates and evidence links.
- Weekly check-in: short, mostly deterministic flow (which commitments were done, what blocked you, next commitment), small model for the reflective reply.
- Monthly progress note written by the mentor.
- Quarterly review: re-score GAS, a short self-efficacy measure and a short working-alliance measure; show trends.
- The mentor revisits open commitments naturally in conversation when relevant, without nagging.
- Scheduler in the worker creates due check-ins and in-app notifications (email reminders optional, opt-in).

## 12. Studio (drafting and practice)

- Drafting: the user picks channel, recipient (e.g. CTO, peer, team, recruiter), purpose and key points; the app produces a draft through the full Natural Voice pipeline; the user edits; edits feed the fingerprint with consent.
- Practice (text only for MVP): mock interviews, salary conversations, difficult one-to-ones, architecture review defence. The AI plays the counterpart, then gives structured feedback against a rubric.
- Prohibited: live interview assistance, fake references, impersonating named real people, fabricated credentials. Return a polite refusal with a legitimate alternative.

## 13. Human mentors (basic)

- A mentee can invite a human mentor by email.
- Consent scopes control what the mentor can see (default: only briefs the mentee explicitly approves).
- Pre-session brief generated from goals, commitments and recent progress; the mentee edits and approves it before sharing.
- Mentor can add session notes and agreed commitments, which flow into the mentee's goals.
- Mentors use these tools free.

## 14. Safety

- Risk classes from Stage 1 drive routing:
  - `normal`: standard mentoring.
  - `adjacent_regulated` (employment law, tax, health, mental wellbeing, finance): general information only, clear scope statement, signpost to qualified help (ACAS, a solicitor, GP, NHS 111).
  - `crisis`: bypass persona and model; return a fixed, reviewed message with UK resources (Samaritans 116 123, NHS 111, 999 in an emergency). Never rewritten by Natural Voice.
  - `prohibited`: refusal template plus an alternative.
- Safety policy section sits above persona in the prompt and cannot be overridden by lens configuration or user overrides.
- Output checks: first-person experience or credential claims, fabricated citations, persona leakage of other users' data.
- Clear disclosure in the UI that the user is talking to an AI.
- No emotion recognition from voice or video.
- Retrieved and uploaded content treated as untrusted (prompt-injection defences).

## 15. Privacy and security

- UK GDPR: lawful basis recorded; consent records for sensitive memories, fingerprint learning from edits, and sharing with human mentors; analytics opt-out.
- Data subject rights in the UI: access, export, rectification, deletion (cascade to embeddings, fingerprints, exemplars and logs where feasible).
- Row-level security in Postgres keyed by user (and tenant later).
- Encryption at rest; envelope encryption for sensitive memories and fingerprints with a separate key (local key in dev, Key Vault in prod).
- Audit log for access to personal data and all admin actions.
- Rate limiting per user and per IP. Input size limits. File upload scanning and type checks.
- Secrets only via environment and a secrets manager; never committed.
- No model-provider training on our data (configure accordingly); log prompts only with PII redaction in non-production.
- Adults only; terms state 18+.

## 16. Data model (minimum)

User, Profile, PersonaConfig, Conversation, Message, Memory, Goal, Milestone, Commitment, CheckIn, Review, WritingSample, StyleProfile, Source, Chunk, MentorRelationship, Session, Brief, Feedback, EvalRun, Consent, AuditEvent, Subscription.

Write the SQLAlchemy models and Alembic migrations, include indexes (pgvector HNSW on embeddings, GIN on tsvector), and document the schema in `/docs/schema.md`.

## 17. API (versioned under /v1)

At minimum:

- `POST /v1/conversations`, `GET /v1/conversations/{id}`, `POST /v1/conversations/{id}/messages` (SSE stream)
- `GET/PUT /v1/profile`
- `GET /v1/personas`, `PUT /v1/personas/active` (pin, combine, override)
- `GET/PATCH/DELETE /v1/memories`, `GET /v1/memories/export`
- `CRUD /v1/goals`, `/v1/commitments`, `POST /v1/check-ins`, `GET /v1/reviews`
- `CRUD /v1/writing-samples`, `GET/DELETE /v1/style-profile`
- `POST /v1/studio/drafts`, `POST /v1/studio/practice`
- `POST /v1/mentors/invite`, `GET/POST /v1/briefs`, `POST /v1/sessions/{id}/notes`
- `GET /v1/sources/{id}`
- `POST /v1/feedback`
- `POST /v1/me/export`, `DELETE /v1/me`
- Admin: `/v1/admin/sources`, `/v1/admin/packs`, `/v1/admin/evals`

Generate OpenAPI docs. Typed client for the frontend generated from OpenAPI.

## 18. Frontend structure

Calm, text-led, accessible (WCAG 2.2 AA), mobile-first.

- Onboarding: a 10–12 minute guided conversation (not a long form) capturing role, stack, seniority, goals and one current challenge; shows an editable profile card ("Here's what I understood"); optional CV upload, writing samples and mentor invite; ends with a baseline (GAS on one or two goals, one self-efficacy item) and one concrete commitment.
- Today: next commitment, one-line nudge, start a conversation.
- Conversation: streaming responses, quiet persona indicator ("Mentoring as: senior data architect · change"), inline citations, thumbs and "this doesn't sound like me" feedback.
- Goals and progress: roadmap, commitments, quarterly trend lines.
- Studio: drafting and practice.
- My mentor's notes: memories, profile, fingerprint, consents, export, delete.
- Mentors: invites, briefs, session notes.
- Settings: mode, British/American English, notifications, subscription.
- Admin (role-gated): sources, packs, evaluation results.

## 19. Evaluation

- `/evals` contains 50 scenarios per pack to start (I will add more with domain experts), each with user profile, conversation, expected qualities and a rubric.
- Runner executes scenarios against the current prompts and models, computes deterministic metrics (lint scores, length, citation validity, safety checks) and an LLM-judge score for persona consistency, actionability, context awareness and appropriateness.
- Persona substance test: same question under two lenses must differ in priorities and recommendations.
- Safety suite: credential claims, crisis messages, prohibited requests, prompt-injection in retrieved content.
- Preservation suite for Natural Voice rewrites.
- CI runs a fast smoke subset; full suite runs on demand and nightly. Results stored in `EvalRun` and shown on the admin page.
- Never use AI-detector scores as a metric.

## 20. Build phases

Work in this order. At the end of each phase, stop, summarise what was built, list any decisions you made, show how to run it, and wait for my go-ahead.

**Phase 0: foundations.** Repo layout, Docker Compose, config, logging, database with migrations, auth integration, CI, health checks, ADR template, README. LLM gateway with two providers and a mock provider for tests.

**Phase 1: core mentoring loop.** Profile, onboarding conversation, persona packs and selection, orchestration stages 1–3, conversation UI with streaming, safety routing and output checks, basic memory (extraction, review page, export, delete).

**Phase 2: knowledge and voice.** Encyclopedia ingestion and hybrid retrieval with citations, admin sources page, Natural Voice layers A and B in chat, layer C plus preservation check in Studio drafting, Writing Fingerprint.

**Phase 3: progress.** Goals with GAS, commitments, weekly check-ins, monthly notes, quarterly reviews, Today view, notifications, evaluation runner and admin results page.

**Phase 4: hybrid and launch readiness.** Human mentor invites, consent scopes, briefs and session notes; text-based practice; Stripe subscriptions (Free, Mentor, Mentor + Human); data subject rights end to end; audit log views; security hardening; Azure infrastructure as code; deployment guide.

Out of scope for the MVP (do not build unless I ask): native mobile apps, voice practice, multi-agent "mentor council", medical/legal/finance/teaching packs, employer team dashboards, per-user fine-tuning.

## 21. Engineering standards

- Type hints everywhere; mypy strict on the backend; strict TypeScript on the frontend.
- Unit tests for every module; integration tests for the orchestration pipeline using the mock LLM provider; Playwright end-to-end tests for onboarding and a mentoring conversation.
- Prompts stored as versioned template files, not inline strings. Every prompt change is recorded and evaluated.
- Record significant decisions as ADRs in `/docs/adr`.
- Cost and latency tracked per route; log a warning if a turn exceeds budget.
- No secrets, real personal data or copyrighted content in the repo.
- Prefer boring, well-maintained libraries. Justify any new dependency in one line in the PR or commit message.

## 22. How to work with me

- Start by restating the plan for Phase 0 in a few lines and listing any questions. Then build.
- Make small, reviewable commits with clear messages.
- If a requirement here conflicts with good engineering, say so and propose the simpler alternative before implementing.
- Never silently skip tests or safety checks to make something work.
- When you need content, credentials or decisions from me (API keys, starter encyclopedia content, pack details, auth provider choice), ask.
