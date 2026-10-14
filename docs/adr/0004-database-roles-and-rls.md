# 0004. Two database roles and row-level security

Date: 2026-10-14
Status: accepted

## Context

This product stores career, goal and communication data about individuals. A forgotten `WHERE user_id = ...` in application code should not become a data leak.

## Decision

Two roles. `mentor` owns the schema and runs migrations. `mentor_app` is what the API and worker connect as; it is neither superuser nor table owner, so row-level security applies to it. Each request runs in one transaction that sets `app.current_user_id`, and every user-owned table has a policy comparing its owner column with that setting. The `audit_events` and `consents` tables grant the runtime role only SELECT and INSERT, so they are append-only.

Provisioning a new user cannot satisfy a policy that needs an existing user id. It goes through a `SECURITY DEFINER` function, `identity_provision_user`, which is the only way the runtime role can create a user.

The tests connect as `mentor_app` and assert that users cannot read or change each other's rows and cannot edit the ledgers.

## Consequences

Every new user-owned table needs a policy and explicit grants in its migration. Background jobs must set the user context before touching user data. In production the migration role needs permission to create the `vector` extension; managed Postgres services allow this for their admin role or by allow-listing the extension. Nothing here replaces application-level authorisation, it backs it up.
