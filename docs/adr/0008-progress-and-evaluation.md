# 8. Progress tracking and evaluation

Status: accepted

## Context

The product promises measurable progress, so it needs a way to set goals, record movement against them and show the user the evidence. It also needs a way to tell whether a change to a prompt, pack or model made the mentoring better or worse.

## Decisions

**Goal Attainment Scaling.** A goal has five described levels, -2 to +2, written by the user (the mentor can suggest wording, never decide it). A score is a position on those levels, with the baseline fixed when the goal is created. This keeps goals personal and comparable over time without pretending they share a unit.

**Commitments and weekly check-ins.** A commitment is small and dated. A check-in is created lazily per week (weeks start on Monday, Europe/London), records an outcome per open commitment, and produces a short reply. The reply is checked by the same safety rules as chat before it is shown.

**Reviews.** Baseline, monthly and quarterly reviews are stored with their scores. The self-efficacy and working-alliance questions are three short items of our own writing. They are not validated instruments, the interface says so, and they are only used to show a user their own trend.

**Notifications.** In-app notifications carry a dedupe key so a scheduler rerun cannot send the same one twice. Email reminders are opt-in, say only that a check-in is due, and never include goal or memory text.

**Scheduler.** One hourly Arq job asks the database, through a SECURITY DEFINER function, which users exist, then works on each user under that user's own row-level security context. A failure for one user is logged and does not stop the rest.

**Evaluation.** Scenarios live in `/evals` as YAML. A smoke run uses a scripted model and checks deterministic things: which lens was picked, what went into the prompt, safety routing, that sources are cited only when retrieved, that facts survive a rewrite. It needs no keys and runs in the test suite. A full run uses real models and a rubric-based judge, stores results in `eval_runs`, and costs money. Evaluation users are synthetic (`eval|...`) and deleted afterwards, and retrieval during evaluation is restricted to fixture sources so the result does not depend on what else is in the database.

## Consequences

Scores are only as honest as the levels the user wrote. The 63 shipped scenarios are fewer than the 50 per pack the plan aimed for; they should grow as real failures are found. Smoke passing says the plumbing is right, not that the mentoring is good; only full runs and expert review say that.
