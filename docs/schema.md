# Database schema

Phase 0 creates the identity and audit tables. Later phases add the rest of the data model from the build specification, each with its own migration, row-level security policy and grants.

All tables use UUID primary keys. Timestamps are `timestamptz`. Migrations live in `apps/api/alembic/versions/`.

## Extensions and functions

- `vector` (pgvector), installed now, used from Phase 2.
- `app_current_user_id()` returns the user id set for the current transaction, or null.
- `identity_provision_user(subject, email)` creates or finds a user. `SECURITY DEFINER`, executable by the runtime role. Returns `(id, created)`.

## users

| Column | Notes |
|---|---|
| id | primary key |
| auth_subject | the identity provider's `sub`, unique |
| email, display_name | optional |
| status | `active`, `suspended` or `deleted` |
| created_at, updated_at, deletion_requested_at | |

Policy: a user can read and update only their own row. The runtime role cannot insert or delete.

## consents

Append-only ledger of consent decisions. The latest row per `(user_id, purpose)` is the current state. `granted` is true or false, and `policy_version` records which text the user saw. Runtime role: SELECT and INSERT only, own rows only.

## audit_events

Append-only record of access to personal data and admin actions: `user_id` (whose data), `actor_id` (who acted), `action`, `resource_type`, `resource_id`, a `metadata` JSON object and `created_at`. Runtime role: SELECT and INSERT only, own rows only. Admin views will use a separate role in Phase 4.

## profiles

One row per user. `role_family`, `seniority`, `job_title`, `years_experience`, `stack` (JSON list), `goals_summary`, `current_challenge`, `english_variant` (`en-GB` or `en-US`), `writing_mode`, `onboarding_status` (`not_started`, `in_progress`, `complete`). Row-level security by `user_id`.

## persona_configs

One row per user: `mode` (`auto` or `pinned`), up to two `lens_ids` and their normalised `weights`. No row means automatic selection.

## conversations and messages

A conversation has a `kind` (`onboarding` or `mentoring`), a `title`, a `rolling_summary` and `summarised_message_count`. A message has a `role`, `content` and a `meta` JSON object recording how the reply was made: persona snapshot, route, provider and model, token usage, cost, latency, intent, risk class, safety flags, prompt versions, section token counts, and `interrupted` or `fixed_reply` where they apply. Deleting a conversation deletes its messages.

## memories

Typed durable facts: `type` (goal_context, decision, commitment, achievement, preference, improvement_area, project, advice_given), `content`, `confidence`, `sensitivity` (`normal` or `sensitive`), `status` (`active` or `pending`), the source message and conversation, and `last_confirmed_at` and `expires_at`. Sensitive memories keep `content` empty and store the text in `content_encrypted`; a check constraint enforces this. Embeddings are added in Phase 2.

All of these tables enable row-level security with a policy on `user_id` and grant the runtime role SELECT, INSERT, UPDATE and DELETE.

## sources and chunks (the Mentor Encyclopedia)

Shared, not per user. A source has a `slug`, `title`, `url`, `publisher`, `authority_tier` (official, standard, peer_reviewed, expert_authored, community), `volatility` (stable, moderate, volatile), `domain`, `subtopic`, `jurisdiction`, `licence`, `reviewer`, `published_date`, `last_reviewed`, `status` (draft, active, retired), `content_hash`, `chunk_count` and `review_flags`. A chunk holds the text, its heading path, a token estimate, the domain, an `embedding vector(1536)` (nullable) and a generated `tsv` column. Indexes: HNSW on the embedding (cosine), GIN on `tsv`, and a unique `(source_id, ordinal)`.

Row-level security: `status = 'active'` rows are readable by everyone; everything else, and all writes, need `app_is_admin()`.

## writing_samples, style_profiles, drafts, feedback

`writing_samples` stores text the user wrote, encrypted, with its channel, word count and origin (`user_provided` or `draft_edit`). `style_profiles` holds one row per user: the stylometric features per channel and overall, the generated voice cards, an optional user-written override, and the sample count. `drafts` holds Studio drafts with their lint report, similarity and metadata. `feedback` holds thumbs and "doesn't sound like me" signals against a message or a draft. All four are private to the user by row-level security.

## Planned (not yet created)

Goals, milestones, commitments, check-ins and reviews (Phase 3); mentor relationships, sessions and briefs, evaluation runs, subscriptions (Phases 3 and 4).
