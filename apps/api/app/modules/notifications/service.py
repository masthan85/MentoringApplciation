import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.email import get_email_sender
from app.core.errors import NotFound
from app.modules.notifications.models import Notification
from app.modules.profile.models import Profile

log = logging.getLogger(__name__)


async def notify(
    session: AsyncSession,
    user_id: UUID,
    *,
    kind: str,
    title: str,
    dedupe_key: str,
    body: str | None = None,
    link: str | None = None,
    email_to: str | None = None,
) -> Notification | None:
    """Create a notification once per ``dedupe_key``. Returns None if it already existed.

    If ``email_to`` is given (the user opted in) a short reminder is emailed, with a link and no private detail.
    """
    result = await session.execute(
        insert(Notification)
        .values(
            user_id=user_id, kind=kind, title=title, body=body, link=link, dedupe_key=dedupe_key
        )
        .on_conflict_do_nothing(constraint="uq_notifications_user_dedupe")
        .returning(Notification.id)
    )
    row = result.first()
    if row is None:
        return None
    notification = (
        await session.execute(select(Notification).where(Notification.id == row.id))
    ).scalar_one()
    if email_to:
        try:
            url = f"{get_settings().public_web_url}{link or ''}"
            await get_email_sender().send(
                email_to,
                title,
                f"{title}\n\n{body or ''}\n\nOpen Mentor: {url}\n\nYou can switch these emails off in Settings.",
            )
            notification.emailed_at = datetime.now(UTC)
        except Exception:
            log.warning("reminder email failed", exc_info=True)
    return notification


async def list_notifications(
    session: AsyncSession, user_id: UUID, limit: int = 30
) -> list[Notification]:
    rows = await session.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def unread_count(session: AsyncSession, user_id: UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            )
        ).scalar_one()
    )


async def mark_read(session: AsyncSession, user_id: UUID, notification_id: UUID | None) -> int:
    query = update(Notification).where(
        Notification.user_id == user_id, Notification.read_at.is_(None)
    )
    if notification_id:
        query = query.where(Notification.id == notification_id)
    result = await session.execute(query.values(read_at=datetime.now(UTC)))
    count: int = result.rowcount  # type: ignore[attr-defined]
    if notification_id and count == 0:
        exists = (
            await session.execute(
                select(Notification.id).where(
                    Notification.id == notification_id, Notification.user_id == user_id
                )
            )
        ).first()
        if exists is None:
            raise NotFound("Notification not found")
    return count


async def wants_email(session: AsyncSession, user_id: UUID) -> bool:
    return bool(
        (
            await session.execute(select(Profile.email_reminders).where(Profile.user_id == user_id))
        ).scalar_one_or_none()
    )
