from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.modules.orchestration.models import Conversation, Message


async def get_conversation(
    session: AsyncSession, user_id: UUID, conversation_id: UUID
) -> Conversation:
    conversation = (
        await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise NotFound("Conversation not found")
    return conversation


async def create_conversation(
    session: AsyncSession, user_id: UUID, kind: str, title: str | None = None
) -> Conversation:
    if kind == "onboarding":
        existing = (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id, Conversation.kind == "onboarding")
                .order_by(Conversation.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing  # one onboarding conversation per user; resume it
    conversation = Conversation(user_id=user_id, kind=kind, title=title)
    session.add(conversation)
    await session.flush()
    return conversation


async def list_conversations(
    session: AsyncSession, user_id: UUID, limit: int = 50
) -> list[Conversation]:
    rows = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    return list(rows.scalars())


async def list_messages(session: AsyncSession, conversation_id: UUID) -> list[Message]:
    rows = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    return list(rows.scalars())


async def recent_messages(
    session: AsyncSession, conversation_id: UUID, limit: int
) -> list[Message]:
    rows = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    return list(reversed(list(rows.scalars())))


async def count_messages(session: AsyncSession, conversation_id: UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Message)
                .where(Message.conversation_id == conversation_id)
            )
        ).scalar_one()
    )


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role=role,
        content=content,
        meta=meta or {},
    )
    session.add(message)
    if role == "user" and not conversation.title:
        conversation.title = " ".join(content.split())[:60]
    conversation.updated_at = func.now()
    await session.flush()
    return message


async def delete_conversation(session: AsyncSession, user_id: UUID, conversation_id: UUID) -> None:
    conversation = await get_conversation(session, user_id, conversation_id)
    await session.delete(conversation)
