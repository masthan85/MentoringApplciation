import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.audit import service as audit
from app.modules.subscriptions.entitlements import PLANS
from app.modules.subscriptions.models import StripeEvent, Subscription

log = logging.getLogger(__name__)


def plan_for_price(price_id: str | None) -> str | None:
    settings = get_settings()
    if price_id and price_id == settings.stripe_price_mentor_human:
        return "mentor_human"
    if price_id and price_id == settings.stripe_price_mentor:
        return "mentor"
    return None


async def _subscription(session: AsyncSession, user_id: UUID) -> Subscription:
    sub = (
        await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user_id, plan="free", status="active")
        session.add(sub)
    return sub


def _period_end(obj: dict[str, Any]) -> datetime | None:
    stamp = obj.get("current_period_end")
    if stamp is None:
        items = (obj.get("items") or {}).get("data") or []
        stamp = items[0].get("current_period_end") if items else None
    return datetime.fromtimestamp(int(stamp), UTC) if stamp else None


async def _user_for(session: AsyncSession, obj: dict[str, Any]) -> UUID | None:
    raw = (obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id")
    if raw:
        try:
            return UUID(str(raw))
        except ValueError:
            return None
    customer = obj.get("customer")
    if customer:
        return (
            await session.execute(
                select(Subscription.user_id).where(Subscription.stripe_customer_id == customer)
            )
        ).scalar_one_or_none()
    return None


async def apply_event(session: AsyncSession, event: dict[str, Any]) -> str:
    """Apply a verified Stripe event. Returns what happened, for logging and tests."""
    event_id, kind = str(event.get("id", "")), str(event.get("type", ""))
    seen = await session.execute(
        insert(StripeEvent)
        .values(id=event_id, type=kind)
        .on_conflict_do_nothing()
        .returning(StripeEvent.id)
    )
    if seen.first() is None:
        return "duplicate"
    obj = (event.get("data") or {}).get("object") or {}
    user_id = await _user_for(session, obj)
    if user_id is None:
        return "ignored: no matching user"

    if kind == "checkout.session.completed":
        plan = (obj.get("metadata") or {}).get("plan")
        if plan not in PLANS:
            return "ignored: unknown plan"
        sub = await _subscription(session, user_id)
        sub.plan, sub.status = plan, "active"
        sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
        sub.stripe_subscription_id = obj.get("subscription") or sub.stripe_subscription_id
        sub.updated_at = datetime.now(UTC)
        await audit.record(session, "billing.subscribed", user_id=user_id, metadata={"plan": plan})
        return "subscribed"

    if kind in ("customer.subscription.updated", "customer.subscription.created"):
        sub = await _subscription(session, user_id)
        items = (obj.get("items") or {}).get("data") or []
        price = ((items[0].get("price") or {}).get("id")) if items else None
        plan = plan_for_price(price) or (obj.get("metadata") or {}).get("plan") or sub.plan
        sub.plan = plan if plan in PLANS else sub.plan
        sub.status = str(obj.get("status", sub.status))
        sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
        sub.stripe_subscription_id = obj.get("id") or sub.stripe_subscription_id
        sub.current_period_end = _period_end(obj)
        sub.updated_at = datetime.now(UTC)
        return "updated"

    if kind == "customer.subscription.deleted":
        sub = await _subscription(session, user_id)
        sub.plan, sub.status = "free", "canceled"
        sub.current_period_end = None
        sub.updated_at = datetime.now(UTC)
        await audit.record(session, "billing.cancelled", user_id=user_id)
        return "cancelled"

    return "ignored: event type"
