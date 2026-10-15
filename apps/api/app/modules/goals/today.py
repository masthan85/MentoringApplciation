"""The Today view: what to do next, in one glance."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.goals import checkin, reviews, service
from app.modules.goals.models import CheckIn, Commitment, Goal
from app.modules.notifications.service import unread_count
from app.modules.profile.models import Profile


def nudge(
    *,
    check_in_due: bool,
    overdue: int,
    open_count: int,
    quarterly_due: bool,
    next_commitment: Commitment | None,
) -> dict[str, str]:
    if check_in_due:
        return {
            "kind": "check_in",
            "text": "Your weekly check-in takes about five minutes.",
            "link": "/check-in",
        }
    if overdue:
        noun = "commitment is" if overdue == 1 else "commitments are"
        return {
            "kind": "overdue",
            "text": f"{overdue} {noun} past the date. Update them or move them.",
            "link": "/goals",
        }
    if quarterly_due:
        return {"kind": "review", "text": "Your quarterly review is ready.", "link": "/review"}
    if open_count == 0:
        return {
            "kind": "commit",
            "text": "What is one small thing you could commit to this week?",
            "link": "/goals",
        }
    if next_commitment is not None:
        when = f" by {next_commitment.due_date.isoformat()}" if next_commitment.due_date else ""
        return {
            "kind": "next",
            "text": f"Next up: {next_commitment.title}{when}.",
            "link": "/goals",
        }
    return {"kind": "none", "text": "", "link": "/chat"}


async def build_today(
    session: AsyncSession, user_id: UUID, *, today: date | None = None
) -> dict[str, Any]:
    if today is None:
        tz = (
            await session.execute(select(Profile.timezone).where(Profile.user_id == user_id))
        ).scalar_one_or_none()
        today = checkin.today_in(tz)
    open_rows = list(
        (
            await session.execute(
                select(Commitment)
                .where(Commitment.user_id == user_id, Commitment.status == "open")
                .order_by(Commitment.due_date.nulls_last(), Commitment.created_at)
            )
        ).scalars()
    )
    overdue = [c for c in open_rows if c.due_date and c.due_date < today]
    next_commitment = overdue[0] if overdue else (open_rows[0] if open_rows else None)
    start = checkin.week_start(today)
    current = (
        await session.execute(
            select(CheckIn).where(CheckIn.user_id == user_id, CheckIn.week_start == start)
        )
    ).scalar_one_or_none()
    goals = list(
        (
            await session.execute(
                select(Goal)
                .where(Goal.user_id == user_id, Goal.status == "active")
                .order_by(Goal.created_at)
            )
        ).scalars()
    )
    check_in_due = bool(goals or open_rows) and (current is None or current.status == "due")
    quarterly = await reviews.quarterly_status(session, user_id, today=today)
    return {
        "next_commitment": (
            {
                "id": str(next_commitment.id),
                "title": next_commitment.title,
                "due_date": next_commitment.due_date.isoformat()
                if next_commitment.due_date
                else None,
                "overdue": next_commitment in overdue,
            }
            if next_commitment
            else None
        ),
        "nudge": nudge(
            check_in_due=check_in_due,
            overdue=len(overdue),
            open_count=len(open_rows),
            quarterly_due=bool(quarterly["due"]),
            next_commitment=next_commitment,
        ),
        "check_in_due": check_in_due,
        "quarterly_review_due": bool(quarterly["due"]),
        "goals": [
            {
                "id": str(g.id),
                "title": g.title,
                "current_score": g.current_score,
                "baseline_score": g.baseline_score,
                "level_text": g.gas_levels.get(str(g.current_score), ""),
                "target_date": g.target_date.isoformat() if g.target_date else None,
            }
            for g in goals
        ],
        "open_commitments": len(open_rows),
        "unread_notifications": await unread_count(session, user_id),
    }


__all__ = ["build_today", "nudge", "service"]
