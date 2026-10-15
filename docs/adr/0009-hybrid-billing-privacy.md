# 9. Human mentors, billing and privacy

Status: accepted

## Context

Phase 4 adds human mentors, paid plans and the controls people need over their data. Each of them touches personal data, so the rules have to be enforced by the database and not only by the application.

## Decisions

**A mentor sees only what the mentee approves.** Mentors do not read the mentee's tables. They read one thing, an approved brief, through a `SECURITY DEFINER` function that checks the link is active and the brief approved, and writes an audit event for the mentee. A brief is built only from goals and commitments the mentee allowed, never memories, conversations, check-in blockers or writing samples, and any edit withdraws approval. Ending a link deletes its briefs.

**Mentors propose, mentees decide.** A mentor's session notes arrive through another audited function. Actions in them become commitments with status `proposed`, which do nothing until the mentee accepts. Accepting a mentor invitation needs the token and an account with the email the mentee named.

**Practice is rehearsal, not assistance.** Practice conversations use a role-play prompt that plays a generic person, never a named one. The same safety rules run before any model, so a request for live interview help is refused even inside a rehearsal. Nothing from a rehearsal becomes a memory.

**Billing is optional and fails safe.** With `BILLING_ENABLED` off everyone has everything, which keeps development and any self-hosted use simple. With it on, the plan comes from a `subscriptions` row that only the Stripe webhook (signed, five-minute tolerance, replay-safe by event id) can write. Access lapses when the paid period ends. The free plan has a daily message limit; studio, practice and the human mentor link are paid features.

**Deleting an account is a database operation.** One `SECURITY DEFINER` function deletes the user and everything cascades. The audit trail keeps the fact of the deletion but loses the link to the person. Export is a JSON file of the user's own rows, with encrypted fields decrypted for them and internal tokens and vectors left out. Users can see who accessed their data; admins can read the full audit log, and reading it is itself logged.

**Hardening.** Every response carries security headers, bodies over 1 MB are refused, log lines have emails, long numbers and bearer tokens redacted, and a single upload gate (`app/core/uploads.py`) checks type, size, active content and an optional ClamAV scan, failing closed.

## Consequences

No route accepts uploads yet, so the upload gate is tested but unused. The web CSP allows inline scripts until nonces are added. The Azure templates are unvalidated. The mentor-invitation email is not sent automatically; the mentee is shown a link to pass on, which avoids sending unsolicited email on a user's behalf.
