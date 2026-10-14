from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import set_current_user
from app.core.errors import Forbidden
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.identity.models import Consent, User


async def get_or_provision_user(session: AsyncSession, principal: Principal) -> User:
    """Find the user for a verified token subject, creating them on first sign-in.

    Provisioning goes through a SECURITY DEFINER function because the runtime
    role cannot insert into ``users`` directly (row-level security).
    """
    row = (
        await session.execute(
            text("SELECT id, created FROM identity_provision_user(:subject, :email)"),
            {"subject": principal.subject, "email": principal.email},
        )
    ).one()
    user_id, created = row.id, row.created
    await set_current_user(session, user_id)
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    if user.status != "active":
        raise Forbidden("This account is not active")
    if created:
        await audit.record(session, "user.provisioned", user_id=user_id, resource_type="user")
    return user


CONSENT_PURPOSES = ("sensitive_memory", "fingerprint_learning", "mentor_sharing", "analytics")
POLICY_VERSION = "2026-10-draft"


async def consent_state(session: AsyncSession, user_id: object) -> dict[str, bool]:
    """Latest decision per purpose. Purposes never answered are false."""
    rows = (
        await session.execute(
            select(Consent)
            .where(Consent.user_id == user_id)
            .order_by(Consent.created_at.desc(), Consent.id)
        )
    ).scalars()
    state = dict.fromkeys(CONSENT_PURPOSES, False)
    seen: set[str] = set()
    for row in rows:
        if row.purpose in state and row.purpose not in seen:
            state[row.purpose] = row.granted
            seen.add(row.purpose)
    return state


async def set_consent(session: AsyncSession, user: User, purpose: str, granted: bool) -> None:
    session.add(
        Consent(user_id=user.id, purpose=purpose, granted=granted, policy_version=POLICY_VERSION)
    )
    await audit.record(
        session,
        "consent.granted" if granted else "consent.withdrawn",
        user_id=user.id,
        resource_type="consent",
        resource_id=purpose,
    )
    await session.flush()
