"""The scheduler: due check-ins, commitment reminders, monthly notes and quarterly reviews.

Everything here is idempotent, so running it every hour, or twice, never duplicates anything.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text

from app.core.db import session_scope
from app.core.jobs import job
from app.modules.goals import checkin, reviews
from app.modules.goals.models import Commitment, Goal
from app.modules.identity.models import User
from app.modules.notifications.service import notify
from app.modules.profile.models import Profile

log = logging.getLogger("app.scheduler")


async def process_user(user_id: UUID, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(UTC)
    counts = {"notifications": 0, "monthly_notes": 0}
    today = checkin.today_london(now)
    async with session_scope(user_id) as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        profile = (
            await session.execute(select(Profile).where(Profile.user_id == user_id))
        ).scalar_one_or_none()
        email_to = user.email if profile and profile.email_reminders and user.email else None

        async def send(**kwargs: Any) -> None:
            if await notify(session, user_id, email_to=email_to, **kwargs):
                counts["notifications"] += 1

        goals = (
            (
                await session.execute(
                    select(Goal).where(Goal.user_id == user_id, Goal.status == "active")
                )
            )
            .scalars()
            .all()
        )
        open_rows = (
            (
                await session.execute(
                    select(Commitment).where(
                        Commitment.user_id == user_id, Commitment.status == "open"
                    )
                )
            )
            .scalars()
            .all()
        )

        # 1. The weekly check-in.
        if goals or open_rows:
            current = await checkin.current_check_in(session, user, today=today)
            if current.status == "due":
                await send(
                    kind="check_in",
                    title="Your weekly check-in is ready",
                    body="It takes about five minutes.",
                    link="/check-in",
                    dedupe_key=f"checkin:{current.week_start}",
                )

        # 2. Commitments that are due or late. One reminder each, never a stream of them.
        for commitment in open_rows:
            if commitment.due_date is None:
                continue
            if commitment.due_date in (today, today + timedelta(days=1)):
                when = "today" if commitment.due_date == today else "tomorrow"
                await send(
                    kind="commitment_due",
                    title=f"Due {when}: {commitment.title}",
                    link="/goals",
                    dedupe_key=f"due:{commitment.id}:{commitment.due_date}",
                )
            elif commitment.due_date < today:
                await send(
                    kind="commitment_overdue",
                    title=f"Past its date: {commitment.title}",
                    body="Mark it done, move it, or drop it.",
                    link="/goals",
                    dedupe_key=f"overdue:{commitment.id}",
                )

        # 3. The monthly note for last month, in the first week of this one.
        if today.day <= 7:
            previous = today.replace(day=1) - timedelta(days=1)
            note = await reviews.generate_monthly_note(session, user_id, previous)
            if note is not None:
                counts["monthly_notes"] += 1
                await send(
                    kind="monthly_note",
                    title=f"Your progress note for {previous.strftime('%B')}",
                    link="/review",
                    dedupe_key=f"monthly:{note.period_start}",
                )

        # 4. A quarterly review, once per quarter.
        status = await reviews.quarterly_status(session, user_id, today=today)
        if status["due"] and goals:
            await send(
                kind="quarterly_review",
                title="Your quarterly review is ready",
                body="Re-score your goals and see how far you have come.",
                link="/review",
                dedupe_key=f"quarterly:{status['since']}",
            )
    return counts


async def run_scheduler(now: datetime | None = None) -> dict[str, int]:
    totals = {"users": 0, "notifications": 0, "monthly_notes": 0, "errors": 0}
    async with session_scope() as session:
        ids = [row[0] for row in (await session.execute(text("SELECT scheduler_user_ids()"))).all()]
    for user_id in ids:
        totals["users"] += 1
        try:
            counts = await process_user(user_id, now)
        except Exception:
            totals["errors"] += 1
            log.exception("scheduler failed for one user", extra={"user_id": str(user_id)})
            continue
        totals["notifications"] += counts["notifications"]
        totals["monthly_notes"] += counts["monthly_notes"]
    log.info("scheduler tick", extra=totals)
    return totals


@job("scheduler_tick")
async def scheduler_tick() -> None:
    await run_scheduler()
