"""The weekly check-in: a short, mostly deterministic flow with one small-model reply."""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.modules.audit import service as audit
from app.modules.goals import service
from app.modules.goals.models import CheckIn, Commitment
from app.modules.goals.schemas import CheckInComplete, CommitmentIn
from app.modules.identity.models import User
from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.safety import CRISIS_MESSAGE, Risk, check_output, scan
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
LONDON = ZoneInfo("Europe/London")
REPLY_PROMPT = ("checkin_reply", 1)


def today_london(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(LONDON).date()


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


async def current_check_in(
    session: AsyncSession, user: User, *, today: date | None = None
) -> CheckIn:
    start = week_start(today or today_london())
    existing = (
        await session.execute(
            select(CheckIn).where(CheckIn.user_id == user.id, CheckIn.week_start == start)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    check_in = CheckIn(user_id=user.id, week_start=start)
    session.add(check_in)
    await session.flush()
    return check_in


async def get_check_in(session: AsyncSession, user_id: Any, check_in_id: Any) -> CheckIn:
    row = (
        await session.execute(
            select(CheckIn).where(CheckIn.id == check_in_id, CheckIn.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Check-in not found")
    return row


def _facts(
    updates: list[tuple[Commitment, str, str | None]],
    blockers: str | None,
    next_title: str | None,
    next_due: date | None,
) -> str:
    lines = []
    done = [c.title for c, outcome, _ in updates if outcome == "done"]
    partial = [c.title for c, outcome, _ in updates if outcome == "partial"]
    missed = [c.title for c, outcome, _ in updates if outcome == "missed"]
    dropped = [c.title for c, outcome, _ in updates if outcome == "dropped"]
    if done:
        lines.append("Done: " + "; ".join(done))
    if partial:
        lines.append("Partly done: " + "; ".join(partial))
    if missed:
        lines.append("Not done: " + "; ".join(missed))
    if dropped:
        lines.append("Dropped on purpose: " + "; ".join(dropped))
    for commitment, _, note in updates:
        if note:
            lines.append(f"Note on '{commitment.title}': {note}")
    lines.append(f"Blocker they named: {blockers}" if blockers else "No blocker named.")
    if next_title:
        lines.append(
            f"Next commitment: {next_title}" + (f" by {next_due.isoformat()}" if next_due else "")
        )
    else:
        lines.append("They did not set a next commitment.")
    return "\n".join(lines)


def fallback_reply(
    updates: list[tuple[Commitment, str, str | None]], next_title: str | None, next_due: date | None
) -> str:
    done = sum(1 for _, o, _ in updates if o == "done")
    parts = [
        f"Thanks for checking in. You finished {done} of {len(updates)} commitments this week."
        if updates
        else "Thanks for checking in."
    ]
    if next_title:
        parts.append(
            f"Next up: {next_title}" + (f", by {next_due.isoformat()}." if next_due else ".")
        )
    return " ".join(parts)


async def complete_check_in(
    session: AsyncSession, user: User, check_in: CheckIn, body: CheckInComplete
) -> tuple[CheckIn, str | None]:
    """Apply the user's answers deterministically, then write a short reply. Returns (check_in, safety_message)."""
    if check_in.status == "completed":
        raise AppError("This check-in is already complete.")
    free_text = " ".join(
        filter(
            None,
            [
                body.blockers,
                *[u.note for u in body.updates],
                body.next_commitment.title if body.next_commitment else None,
            ],
        )
    )
    hit = scan(free_text) if free_text else None
    updates: list[tuple[Commitment, str, str | None]] = []
    for update in body.updates:
        commitment = await service.get_commitment(session, user.id, update.commitment_id)
        if commitment.status != "open":
            raise AppError(f"'{commitment.title}' is not an open commitment.")
        service.apply_status(commitment, update.outcome)
        if update.note:
            commitment.evidence_note = update.note
        updates.append((commitment, update.outcome, update.note))
    next_title = next_due = None
    if body.next_commitment:
        created = await service.create_commitment(
            session,
            user.id,
            CommitmentIn(
                title=body.next_commitment.title,
                due_date=body.next_commitment.due_date,
                goal_id=body.next_commitment.goal_id,
            ),
        )
        next_title, next_due = created.title, created.due_date
    check_in.status = "completed"
    check_in.completed_at = datetime.now(UTC)
    check_in.responses = {
        "updates": [
            {"commitment_id": str(u.commitment_id), "outcome": u.outcome} for u in body.updates
        ],
        "blockers": body.blockers,
        "next_commitment": body.next_commitment.model_dump(mode="json")
        if body.next_commitment
        else None,
    }
    safety: str | None = None
    if hit and hit.risk is Risk.CRISIS:
        safety = CRISIS_MESSAGE
        check_in.reply = None
    else:
        check_in.reply = await _reply(updates, body.blockers, next_title, next_due)
    await audit.record(
        session,
        "check_in.complete",
        user_id=user.id,
        resource_type="check_in",
        resource_id=str(check_in.id),
    )
    await session.flush()
    return check_in, safety


async def _reply(
    updates: list[tuple[Commitment, str, str | None]],
    blockers: str | None,
    next_title: str | None,
    next_due: date | None,
) -> str:
    facts = _facts(updates, blockers, next_title, next_due)
    try:
        result = await current_gateway().complete(
            "chat_small",
            CompletionRequest(
                system=prompts.load(*REPLY_PROMPT),
                messages=[Message("user", f"<facts>\n{facts}\n</facts>")],
                max_tokens=400,
                tags={"purpose": "checkin_reply"},
            ),
        )
    except LLMError:
        return fallback_reply(updates, next_title, next_due)
    text = result.text.strip()
    if not text or check_output(text):
        log.warning("check-in reply discarded by output check")
        return fallback_reply(updates, next_title, next_due)
    return text
