from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


async def record(
    session: AsyncSession,
    action: str,
    *,
    user_id: UUID | None,
    actor_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Add an audit event to the caller's transaction."""
    session.add(
        AuditEvent(
            user_id=user_id,
            actor_id=actor_id or user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=metadata or {},
        )
    )
