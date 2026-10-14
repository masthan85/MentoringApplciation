import json
import time
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from app.core.config import Settings
from app.modules.subscriptions import stripe
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]
SECRET = "whsec_test_secret"


@pytest.fixture
def billing(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    for name, value in {
        "billing_enabled": True,
        "stripe_secret_key": SecretStr("sk_test_x"),
        "stripe_webhook_secret": SecretStr(SECRET),
        "stripe_price_mentor": "price_mentor",
        "stripe_price_mentor_human": "price_human",
        "free_daily_turns": 2,
    }.items():
        monkeypatch.setattr(settings, name, value)
    return settings


def _event(kind: str, obj: dict[str, Any], event_id: str = "evt_1") -> bytes:
    return json.dumps({"id": event_id, "type": kind, "data": {"object": obj}}).encode()


async def _post_event(
    client: httpx.AsyncClient, payload: bytes, secret: str = SECRET, ts: int | None = None
) -> httpx.Response:
    return await client.post(
        "/v1/billing/webhook",
        content=payload,
        headers={
            "stripe-signature": stripe.sign(payload, secret, timestamp=ts),
            "content-type": "application/json",
        },
    )


def test_signature_verification() -> None:
    payload = b'{"id":"evt","type":"x"}'
    header = stripe.sign(payload, SECRET)
    assert stripe.verify_signature(payload, header, SECRET)["id"] == "evt"
    with pytest.raises(ValueError):
        stripe.verify_signature(payload, header, "wrong")
    with pytest.raises(ValueError):
        stripe.verify_signature(payload + b" ", header, SECRET)
    old = stripe.sign(payload, SECRET, timestamp=int(time.time()) - 3600)
    with pytest.raises(ValueError):
        stripe.verify_signature(payload, old, SECRET)
    with pytest.raises(ValueError):
        stripe.verify_signature(payload, "garbage", SECRET)


async def test_with_billing_off_everyone_has_everything(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    body = (await client.get("/v1/billing", headers=auth())).json()
    assert body["billing_enabled"] is False
    assert all(body["features"].values())
    assert (await client.post("/v1/billing/webhook", content=b"{}")).status_code == 404


async def test_free_users_are_limited_and_paid_features_are_gated(
    client: httpx.AsyncClient, auth: Headers, billing: Settings
) -> None:
    h = auth()
    assert (await client.get("/v1/billing", headers=h)).json()["plan"] == "free"
    draft = await client.post(
        "/v1/studio/drafts",
        json={
            "channel": "email",
            "recipient": "manager",
            "purpose": "Ask for time",
            "key_points": "Two days a month.",
        },
        headers=h,
    )
    assert draft.status_code == 402
    assert draft.json()["feature"] == "studio"
    assert (
        await client.post("/v1/practice", json={"scenario_id": "mock_interview"}, headers=h)
    ).status_code == 402
    link = await client.post("/v1/mentor-link", json={"mentor_email": "m@example.com"}, headers=h)
    assert link.status_code == 402

    conversation = (
        await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)
    ).json()
    statuses = []
    for _ in range(3):
        r = await client.post(
            f"/v1/conversations/{conversation['id']}/messages",
            json={"content": "Hello there"},
            headers=h,
        )
        statuses.append(r.status_code)
    assert statuses == [200, 200, 429]


async def test_checkout_completed_then_cancelled_changes_the_plan(
    client: httpx.AsyncClient, auth: Headers, billing: Settings, db: AsyncEngine
) -> None:
    h = auth(sub="payer", email="payer@example.com")
    me = (await client.get("/v1/me", headers=h)).json()
    completed = _event(
        "checkout.session.completed",
        {
            "customer": "cus_1",
            "subscription": "sub_1",
            "metadata": {"user_id": me["id"], "plan": "mentor_human"},
        },
    )
    assert (await _post_event(client, completed)).json() == {"outcome": "subscribed"}
    state = (await client.get("/v1/billing", headers=h)).json()
    assert state["plan"] == "mentor_human"
    assert all(state["features"].values())
    assert state["can_manage"] is True

    # Replaying the same event does nothing.
    assert (await _post_event(client, completed)).json() == {"outcome": "duplicate"}

    period_end = int(time.time()) + 86400 * 30
    updated = _event(
        "customer.subscription.updated",
        {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "active",
            "current_period_end": period_end,
            "items": {"data": [{"price": {"id": "price_mentor"}}]},
            "metadata": {"user_id": me["id"]},
        },
        "evt_2",
    )
    await _post_event(client, updated)
    state = (await client.get("/v1/billing", headers=h)).json()
    assert state["plan"] == "mentor"
    assert state["features"]["human_mentor"] is False

    cancelled = _event(
        "customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1"}, "evt_3"
    )
    await _post_event(client, cancelled)
    assert (await client.get("/v1/billing", headers=h)).json()["plan"] == "free"


async def test_a_bad_signature_changes_nothing(
    client: httpx.AsyncClient, auth: Headers, billing: Settings
) -> None:
    me = (await client.get("/v1/me", headers=auth())).json()
    payload = _event(
        "checkout.session.completed", {"metadata": {"user_id": me["id"], "plan": "mentor"}}
    )
    forged = await _post_event(client, payload, secret="not-the-secret")
    assert forged.status_code == 400
    stale = await _post_event(client, payload, ts=int(time.time()) - 4000)
    assert stale.status_code == 400
    assert (await client.get("/v1/billing", headers=auth())).json()["plan"] == "free"


async def test_an_expired_period_falls_back_to_free(
    client: httpx.AsyncClient, auth: Headers, billing: Settings, db: AsyncEngine
) -> None:
    h = auth()
    me = (await client.get("/v1/me", headers=h)).json()
    async with db.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO subscriptions (user_id, plan, status, current_period_end) "
                "VALUES (:u, 'mentor', 'active', now() - interval '1 day')"
            ),
            {"u": me["id"]},
        )
    assert (await client.get("/v1/billing", headers=h)).json()["plan"] == "free"


async def test_checkout_calls_stripe_with_the_right_price(
    client: httpx.AsyncClient, auth: Headers, billing: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    async def fake_post(path: str, data: dict[str, str]) -> dict[str, Any]:
        seen.update(path=path, data=data)
        return {"url": "https://checkout.example/session"}

    monkeypatch.setattr(stripe, "_post", fake_post)
    r = await client.post("/v1/billing/checkout", json={"plan": "mentor"}, headers=auth())
    assert r.json() == {"url": "https://checkout.example/session"}
    assert seen["data"]["line_items[0][price]"] == "price_mentor"
    assert seen["data"]["metadata[plan]"] == "mentor"
