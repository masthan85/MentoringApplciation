"""What each plan includes, and the checks that enforce it."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import PaymentRequired, RateLimited
from app.core.redis import get_redis
from app.modules.subscriptions.models import Subscription


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    daily_turns: int | None  # None = unlimited
    studio: bool
    practice: bool
    human_mentor: bool


PLANS: dict[str, Plan] = {
    "free": Plan("free", "Free", None, studio=False, practice=False, human_mentor=False),
    "mentor": Plan("mentor", "Mentor", None, studio=True, practice=True, human_mentor=False),
    "mentor_human": Plan(
        "mentor_human", "Mentor + Human", None, studio=True, practice=True, human_mentor=True
    ),
}
FEATURES = ("studio", "practice", "human_mentor")
ACTIVE_STATUSES = ("active", "trialing", "past_due")  # past_due keeps access while Stripe retries


def plan_with_cap(plan: Plan) -> Plan:
    if plan.id == "free":
        return Plan("free", plan.name, get_settings().free_daily_turns, False, False, False)
    return plan


async def current_plan(session: AsyncSession, user_id: UUID) -> Plan:
    """The plan in force. With billing disabled everybody has everything."""
    if not get_settings().billing_enabled:
        return PLANS["mentor_human"]
    sub = (
        await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    ).scalar_one_or_none()
    if sub is None or sub.status not in ACTIVE_STATUSES:
        return plan_with_cap(PLANS["free"])
    if sub.current_period_end and sub.current_period_end < datetime.now(UTC):
        return plan_with_cap(PLANS["free"])
    return plan_with_cap(PLANS.get(sub.plan, PLANS["free"]))


async def require_feature(session: AsyncSession, user_id: UUID, feature: str) -> Plan:
    plan = await current_plan(session, user_id)
    if not getattr(plan, feature):
        raise PaymentRequired(
            "This is part of a paid plan.", extra={"feature": feature, "plan": plan.id}
        )
    return plan


async def check_daily_turns(session: AsyncSession, user_id: UUID) -> None:
    """Count one mentoring turn against the free plan's daily allowance."""
    plan = await current_plan(session, user_id)
    if plan.daily_turns is None:
        return
    key = f"turns:{user_id}:{datetime.now(UTC).date().isoformat()}"
    try:
        redis = get_redis()
        used = await redis.incr(key)
        if used == 1:
            await redis.expire(key, 60 * 60 * 36)
    except Exception:
        return  # a counter outage should not lock people out
    if used > plan.daily_turns:
        raise RateLimited(
            f"You have used today's {plan.daily_turns} free messages. "
            "They reset tomorrow, or you can upgrade."
        )
