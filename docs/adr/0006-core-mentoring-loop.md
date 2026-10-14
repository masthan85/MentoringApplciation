# 0006. Core mentoring loop: decisions made in Phase 1

Date: 2026-10-14
Status: accepted

## Context

Phase 1 builds the first end-to-end mentoring experience. Several choices shaped it and are worth recording.

## Decisions

**Persona is configuration.** Mentor packs are YAML, validated when the API starts (a bad pack stops the process). A lens contributes priorities, questions, failure modes and seniority-specific depth to the prompt. A schema rule rejects first-person perspectives, and a test shows that two lenses produce different substance for the same user, not only a different tone. Selection order of authority is the user's pinned choice, then a confident classifier suggestion (threshold 0.7, configurable), then the default derived from the profile.

**Safety runs before the model.** Deterministic rules catch crisis language and prohibited requests first. A crisis never reaches a model, and neither does the classifier call for it. The classifier can raise a risk level but never lower one set by the rules. Crisis and refusal replies are fixed text, never generated and never rewritten. The crisis wording in `safety/messages.py` is a draft and needs review by a qualified person before launch.

**Output checks do not block a stream.** The checks for first-person experience and credential claims run after the reply has streamed. A failure is recorded on the message (`safety_flags`) and logged. Prevention rests on the safety prompt, and the evaluation suite (Phase 3) is where these checks will fail a build. This is a known gap: a reply that slips through is already on screen.

**Onboarding reads the answer before replying.** Profile extraction runs in parallel with classification and is applied before the prompt is built. Extracting after the reply made the mentor ask again for things it had just been told.

**No connection is held while streaming.** The turn pipeline opens short database transactions around the model call, not across it. If the client disconnects, whatever was already streamed is saved and marked `interrupted`.

**Memory without embeddings, for now.** Memories are typed rows ranked by type, recency and word overlap within a token budget. Embeddings and similarity arrive with the Mentor Encyclopedia in Phase 2, when the vector column and index will be added. Near-duplicates (word overlap of 0.7 or more, same type) update the existing memory instead of adding a new one.

**Sensitive memories are opt-in, encrypted and confirmed.** Without consent they are dropped. With consent they are stored encrypted with a key separate from the database, wait in a pending state until the user keeps them, and a database constraint forbids plain text in the sensitive column. They will never be shared with human mentors (Phase 4).

**Prompts are versioned files with a manifest.** `app/prompts/manifest.json` holds each file's hash. A test fails when a prompt changes without the manifest being regenerated, so changes are always deliberate and visible in review. The evaluation suite will gate them from Phase 3.

**Jobs run in the worker or inline.** `JOBS_MODE=arq` queues to the worker; `inline` runs them in the API process for local work and tests. A failing job never fails the request that queued it.

**Development sign-in only.** `POST /v1/dev/login` exists only when `AUTH_MODE=dev`. The web app's sign-in screen uses it until an identity provider is chosen. Replacing `src/lib/session.ts` is all the web app needs.

## Consequences

The mentor reads a profile card the user can edit, and the user sees which perspective is in use at all times. The main open risks are the draft safety wording, the post-hoc output check, and that nobody has yet judged the mentoring quality of the packs against real users.
