from app.core.db import set_current_user
from app.core.errors import Forbidden
from app.core.security import Principal
from app.modules.audit import service as audit
from app.modules.identity.models import User
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


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
