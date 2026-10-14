"""A very small Stripe client: Checkout, the customer portal and webhook verification.

Only what is needed, over httpx, so it can be tested without the network. Prices and keys come
from settings; nothing here runs unless BILLING_ENABLED is set.
"""

import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError

API = "https://api.stripe.com/v1"
TOLERANCE_SECONDS = 300


class StripeError(AppError):
    status_code = 502
    code = "billing_unavailable"


def verify_signature(
    payload: bytes, header: str, secret: str, *, now: float | None = None
) -> dict[str, Any]:
    """Check a ``Stripe-Signature`` header and return the event, or raise ValueError."""
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    timestamp = parts.get("t")
    if not timestamp or not timestamp.isdigit():
        raise ValueError("missing timestamp")
    candidates = [
        v for k, v in (item.split("=", 1) for item in header.split(",") if "=" in item) if k == "v1"
    ]
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, c) for c in candidates):
        raise ValueError("signature mismatch")
    if abs((now if now is not None else time.time()) - int(timestamp)) > TOLERANCE_SECONDS:
        raise ValueError("timestamp outside tolerance")
    event = json.loads(payload)
    if not isinstance(event, dict):
        raise ValueError("not an event")
    return event


def sign(payload: bytes, secret: str, *, timestamp: int | None = None) -> str:
    """Build a header the way Stripe does. Used by tests and local webhook rehearsal."""
    ts = timestamp if timestamp is not None else int(time.time())
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


async def _post(path: str, data: dict[str, str]) -> dict[str, Any]:
    key = get_settings().stripe_secret_key
    assert key is not None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{API}{path}", data=data, auth=(key.get_secret_value(), "")
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise StripeError("Billing is unavailable just now. Please try again shortly.") from exc
    body = response.json()
    return body if isinstance(body, dict) else {}


async def create_checkout(
    *, user_id: str, email: str | None, price_id: str, plan: str, customer_id: str | None
) -> str:
    base = get_settings().public_web_url
    data = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "success_url": f"{base}/billing?checkout=success",
        "cancel_url": f"{base}/billing?checkout=cancelled",
        "client_reference_id": user_id,
        "metadata[user_id]": user_id,
        "metadata[plan]": plan,
        "subscription_data[metadata][user_id]": user_id,
        "subscription_data[metadata][plan]": plan,
    }
    if customer_id:
        data["customer"] = customer_id
    elif email:
        data["customer_email"] = email
    session = await _post("/checkout/sessions", data)
    return str(session["url"])


async def create_portal(customer_id: str) -> str:
    base = get_settings().public_web_url
    session = await _post(
        "/billing_portal/sessions", {"customer": customer_id, "return_url": f"{base}/billing"}
    )
    return str(session["url"])
