import logging
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.deps import RequestCtx
from app.core.errors import AppError, Conflict, NotFound
from app.modules.profile.service import get_or_create_profile
from app.modules.regions import service as regions
from app.modules.subscriptions import service, stripe
from app.modules.subscriptions.entitlements import FEATURES, current_plan
from app.modules.subscriptions.models import Subscription

log = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])


class BillingOut(BaseModel):
    billing_enabled: bool
    plan: str
    plan_name: str
    daily_turns: int | None
    features: dict[str, bool]
    can_manage: bool


class CheckoutIn(BaseModel):
    plan: Literal["mentor", "mentor_human"]


class UrlOut(BaseModel):
    url: str


@router.get("/v1/billing", response_model=BillingOut)
async def read_billing(ctx: RequestCtx) -> BillingOut:
    plan = await current_plan(ctx.session, ctx.user.id)
    sub = (
        await ctx.session.execute(select(Subscription).where(Subscription.user_id == ctx.user.id))
    ).scalar_one_or_none()
    return BillingOut(
        billing_enabled=get_settings().billing_enabled,
        plan=plan.id,
        plan_name=plan.name,
        daily_turns=plan.daily_turns,
        features={f: bool(getattr(plan, f)) for f in FEATURES},
        can_manage=bool(sub and sub.stripe_customer_id),
    )


@router.post("/v1/billing/checkout", response_model=UrlOut)
async def checkout(body: CheckoutIn, ctx: RequestCtx) -> UrlOut:
    settings = get_settings()
    if not settings.billing_enabled:
        raise NotFound("Billing is not switched on")
    profile_country = (await get_or_create_profile(ctx.session, ctx.user)).country
    plan = await current_plan(ctx.session, ctx.user.id)
    if plan.id == body.plan:
        raise Conflict("You are already on this plan")
    sub = (
        await ctx.session.execute(select(Subscription).where(Subscription.user_id == ctx.user.id))
    ).scalar_one_or_none()
    price = (
        settings.stripe_price_mentor_human
        if body.plan == "mentor_human"
        else settings.stripe_price_mentor
    )
    assert price is not None
    url = await stripe.create_checkout(
        user_id=str(ctx.user.id),
        email=ctx.user.email,
        price_id=price,
        plan=body.plan,
        customer_id=sub.stripe_customer_id if sub else None,
        currency=regions.currency_for(profile_country),
    )
    return UrlOut(url=url)


@router.post("/v1/billing/portal", response_model=UrlOut)
async def portal(ctx: RequestCtx) -> UrlOut:
    if not get_settings().billing_enabled:
        raise NotFound("Billing is not switched on")
    sub = (
        await ctx.session.execute(select(Subscription).where(Subscription.user_id == ctx.user.id))
    ).scalar_one_or_none()
    if sub is None or not sub.stripe_customer_id:
        raise NotFound("There is no subscription to manage")
    return UrlOut(url=await stripe.create_portal(sub.stripe_customer_id))


@router.post("/v1/billing/webhook", include_in_schema=False)
async def webhook(request: Request) -> dict[str, str]:
    settings = get_settings()
    if not settings.billing_enabled or settings.stripe_webhook_secret is None:
        raise NotFound("Billing is not switched on")
    payload = await request.body()
    try:
        event = stripe.verify_signature(
            payload,
            request.headers.get("stripe-signature", ""),
            settings.stripe_webhook_secret.get_secret_value(),
        )
    except ValueError as exc:
        raise AppError("Invalid signature") from exc
    async with session_scope(admin=True) as session:
        outcome = await service.apply_event(session, event)
    log.info("stripe event", extra={"event_type": event.get("type"), "outcome": outcome})
    return {"outcome": outcome}
