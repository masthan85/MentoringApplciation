"""Baseline, monthly progress notes and quarterly reviews, with trends.

The two short measures below are written for this product. They are not validated instruments. Before
outcome claims are made to anyone, replace them with a validated scale used under its licence.
"""

import logging
import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.goals import service
from app.modules.goals.models import CheckIn, Commitment, Goal, GoalScore, Review
from app.modules.goals.schemas import QuarterlyIn
from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.safety import check_output
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
MONTHLY_PROMPT = ("monthly_note", 1)
QUARTER_DAYS = 90

SELF_EFFICACY_ITEMS = [
    "I know what I need to do to reach my next career step.",
    "When I hit an obstacle at work, I can usually work out how to get past it.",
    "I feel confident that I will reach my most important goal this year.",
]
WORKING_ALLIANCE_ITEMS = [
    "The mentor understands what I am trying to achieve.",
    "The mentor's advice helps me take action.",
    "I trust the mentor to be honest with me, even when it is not what I want to hear.",
]


async def record_baseline(session: AsyncSession, user_id: UUID, self_efficacy: int) -> Review:
    existing = (
        await session.execute(
            select(Review).where(Review.user_id == user_id, Review.kind == "baseline")
        )
    ).scalar_one_or_none()
    today = datetime.now(UTC).date()
    if existing is not None:
        existing.scores = {**existing.scores, "self_efficacy": float(self_efficacy)}
        await session.flush()
        return existing
    review = Review(
        user_id=user_id,
        kind="baseline",
        period_start=today,
        period_end=today,
        scores={"self_efficacy": float(self_efficacy)},
    )
    session.add(review)
    await session.flush()
    return review


async def _last_quarterly_end(session: AsyncSession, user_id: UUID) -> date | None:
    return (
        await session.execute(
            select(func.max(Review.period_end)).where(
                Review.user_id == user_id, Review.kind == "quarterly"
            )
        )
    ).scalar_one_or_none()


async def quarterly_status(
    session: AsyncSession, user_id: UUID, *, today: date | None = None
) -> dict[str, Any]:
    """Whether a quarterly review is due, and what it needs."""
    today = today or datetime.now(UTC).date()
    last = await _last_quarterly_end(session, user_id)
    if last is None:
        first_goal = (
            await session.execute(select(func.min(Goal.created_at)).where(Goal.user_id == user_id))
        ).scalar_one_or_none()
        anchor = first_goal.date() if first_goal else None
    else:
        anchor = last
    due = anchor is not None and (today - anchor).days >= QUARTER_DAYS
    goals = (
        (
            await session.execute(
                select(Goal).where(Goal.user_id == user_id, Goal.status == "active")
            )
        )
        .scalars()
        .all()
    )
    return {
        "due": bool(due),
        "since": anchor.isoformat() if anchor else None,
        "goals": [
            {
                "id": str(g.id),
                "title": g.title,
                "current_score": g.current_score,
                "levels": g.gas_levels,
            }
            for g in goals
        ],
        "self_efficacy_items": SELF_EFFICACY_ITEMS,
        "working_alliance_items": WORKING_ALLIANCE_ITEMS,
    }


async def submit_quarterly(
    session: AsyncSession, user_id: UUID, body: QuarterlyIn, *, today: date | None = None
) -> Review:
    today = today or datetime.now(UTC).date()
    goals = {
        g.id: g
        for g in (
            await session.execute(
                select(Goal).where(Goal.user_id == user_id, Goal.status == "active")
            )
        )
        .scalars()
        .all()
    }
    unknown = set(body.gas_scores) - set(goals)
    if unknown:
        raise AppError("One of those goals is not an active goal of yours.")
    missing = set(goals) - set(body.gas_scores)
    if missing:
        raise AppError(
            "Please score every active goal so the review is complete.",
            extra={"missing_goal_ids": [str(m) for m in missing]},
        )
    last = await _last_quarterly_end(session, user_id)
    start = last or (today - timedelta(days=QUARTER_DAYS))
    if last is not None and last >= today:
        raise AppError("You have already completed a review today.")
    for goal_id, score in body.gas_scores.items():
        await service.record_score(
            session, user_id, goals[goal_id], score, "review", body.reflection
        )
    scores: dict[str, Any] = {
        "gas": {str(k): v for k, v in body.gas_scores.items()},
        "self_efficacy": round(statistics.fmean(body.self_efficacy), 2),
        "self_efficacy_items": body.self_efficacy,
        "working_alliance": round(statistics.fmean(body.working_alliance), 2),
        "working_alliance_items": body.working_alliance,
    }
    review = Review(
        user_id=user_id,
        kind="quarterly",
        period_start=start,
        period_end=today,
        content=body.reflection,
        scores=scores,
    )
    session.add(review)
    await audit.record(session, "review.quarterly", user_id=user_id, resource_type="review")
    await session.flush()
    return review


async def list_reviews(
    session: AsyncSession, user_id: UUID, kind: str | None = None
) -> list[Review]:
    query = select(Review).where(Review.user_id == user_id)
    if kind:
        query = query.where(Review.kind == kind)
    return list(
        (
            await session.execute(
                query.order_by(Review.period_end.desc(), Review.created_at.desc())
            )
        ).scalars()
    )


async def trends(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
    """Series for the progress charts: GAS per goal over time, and the two short measures."""
    goals = (
        (
            await session.execute(
                select(Goal)
                .where(Goal.user_id == user_id, Goal.status.in_(("active", "achieved", "paused")))
                .order_by(Goal.created_at)
            )
        )
        .scalars()
        .all()
    )
    scores = (
        (
            await session.execute(
                select(GoalScore)
                .where(GoalScore.user_id == user_id)
                .order_by(GoalScore.recorded_at)
            )
        )
        .scalars()
        .all()
    )
    by_goal: dict[UUID, list[dict[str, Any]]] = {}
    for score in scores:
        by_goal.setdefault(score.goal_id, []).append(
            {
                "at": score.recorded_at.date().isoformat(),
                "score": score.score,
                "source": score.source,
            }
        )
    reviews = await list_reviews(session, user_id)
    efficacy, alliance = [], []
    for review in sorted(reviews, key=lambda r: (r.period_end, r.created_at)):
        if "self_efficacy" in review.scores:
            efficacy.append(
                {
                    "at": review.period_end.isoformat(),
                    "value": review.scores["self_efficacy"],
                    "kind": review.kind,
                }
            )
        if "working_alliance" in review.scores:
            alliance.append(
                {
                    "at": review.period_end.isoformat(),
                    "value": review.scores["working_alliance"],
                    "kind": review.kind,
                }
            )
    return {
        "goals": [
            {"id": str(g.id), "title": g.title, "status": g.status, "points": by_goal.get(g.id, [])}
            for g in goals
        ],
        "self_efficacy": efficacy,
        "working_alliance": alliance,
    }


# ---- monthly note --------------------------------------------------------------------


def month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, next_month - timedelta(days=1)


async def month_facts(
    session: AsyncSession, user_id: UUID, start: date, end: date
) -> dict[str, Any]:
    lo, hi = (
        datetime.combine(start, datetime.min.time(), UTC),
        datetime.combine(end + timedelta(days=1), datetime.min.time(), UTC),
    )
    commitments = (
        (
            await session.execute(
                select(Commitment).where(Commitment.user_id == user_id, Commitment.created_at < hi)
            )
        )
        .scalars()
        .all()
    )
    done = [
        c.title
        for c in commitments
        if c.status in ("done", "partial") and c.completed_at and lo <= c.completed_at < hi
    ]
    missed = [
        c.title
        for c in commitments
        if c.status == "missed" and c.due_date and start <= c.due_date <= end
    ]
    check_ins = (
        await session.execute(
            select(func.count())
            .select_from(CheckIn)
            .where(
                CheckIn.user_id == user_id,
                CheckIn.status == "completed",
                CheckIn.completed_at >= lo,
                CheckIn.completed_at < hi,
            )
        )
    ).scalar_one()
    goals = (
        (
            await session.execute(
                select(Goal).where(Goal.user_id == user_id, Goal.status.in_(("active", "achieved")))
            )
        )
        .scalars()
        .all()
    )
    return {
        "month": start.strftime("%B %Y"),
        "check_ins_completed": int(check_ins),
        "commitments_done": done,
        "commitments_missed": missed,
        "goals": [
            {
                "title": g.title,
                "started_at": g.baseline_score,
                "now": g.current_score,
                "status": g.status,
            }
            for g in goals
        ],
    }


def has_activity(facts: dict[str, Any]) -> bool:
    return bool(
        facts["check_ins_completed"] or facts["commitments_done"] or facts["commitments_missed"]
    )


def fallback_note(facts: dict[str, Any]) -> str:
    done = len(facts["commitments_done"])
    parts = [
        f"In {facts['month']} you completed {facts['check_ins_completed']} weekly check-ins and finished {done} commitments."
    ]
    if facts["commitments_missed"]:
        parts.append(
            f"{len(facts['commitments_missed'])} slipped past their date, so it is worth looking at what got in the way."
        )
    parts.append("Pick one small commitment for the first week of next month and put a date on it.")
    return " ".join(parts)


async def generate_monthly_note(session: AsyncSession, user_id: UUID, month: date) -> Review | None:
    """Write the note for the month containing ``month``. Returns None if it exists or nothing happened."""
    start, end = month_bounds(month)
    if (
        await session.execute(
            select(Review.id).where(
                Review.user_id == user_id, Review.kind == "monthly", Review.period_start == start
            )
        )
    ).first():
        return None
    facts = await month_facts(session, user_id, start, end)
    if not has_activity(facts):
        return None
    text: str | None = None
    try:
        result = await current_gateway().complete(
            "chat_large",
            CompletionRequest(
                system=prompts.load(*MONTHLY_PROMPT),
                messages=[Message("user", f"<facts>\n{facts}\n</facts>")],
                max_tokens=500,
                tags={"purpose": "monthly_note"},
            ),
        )
        text = result.text.strip()
    except LLMError:
        log.warning("monthly note model unavailable; using the plain summary", exc_info=True)
    if not text or check_output(text):
        text = fallback_note(facts)
    review = Review(
        user_id=user_id,
        kind="monthly",
        period_start=start,
        period_end=end,
        content=text,
        scores={"facts": facts},
    )
    session.add(review)
    await session.flush()
    return review
