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

## Planned (not yet created)

Profile, persona configuration, conversations and messages, memories (with pgvector embeddings), goals, milestones, commitments, check-ins, reviews, writing samples and style profiles, sources and chunks (HNSW and GIN indexes), mentor relationships, sessions and briefs, feedback, evaluation runs, subscriptions.
