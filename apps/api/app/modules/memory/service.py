"""Typed memory records: save, dedupe, edit, delete, export."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import AppError, NotFound
from app.modules.audit import service as audit
from app.modules.identity.service import consent_state
from app.modules.memory.models import MEMORY_TYPES, Memory

_WORD = re.compile(r"[a-z0-9]{3,}")
DEDUPE_THRESHOLD = 0.7


@dataclass(frozen=True)
class Candidate:
    type: str
    content: str
    confidence: float
    sensitivity: str


def tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def text_of(memory: Memory) -> str:
    """Plain text of a memory, decrypting sensitive ones. For the owner and the mentor only."""
    if memory.content_encrypted is not None:
        return crypto.decrypt(memory.content_encrypted)
    return memory.content


def present(memory: Memory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "type": memory.type,
        "content": text_of(memory),
        "confidence": memory.confidence,
        "sensitivity": memory.sensitivity,
        "status": memory.status,
        "source_conversation_id": memory.source_conversation_id,
        "created_at": memory.created_at,
        "last_confirmed_at": memory.last_confirmed_at,
    }


async def list_memories(
    session: AsyncSession,
    user_id: UUID,
    *,
    status: str | None = None,
    conversation_id: UUID | None = None,
    since: datetime | None = None,
) -> list[Memory]:
    query = select(Memory).where(Memory.user_id == user_id)
    if status:
        query = query.where(Memory.status == status)
    if conversation_id:
        query = query.where(Memory.source_conversation_id == conversation_id)
    if since:
        query = query.where(Memory.created_at >= since)
    now = datetime.now(UTC)
    rows = (await session.execute(query.order_by(Memory.created_at.desc()))).scalars().all()
    return [m for m in rows if m.expires_at is None or m.expires_at > now]


async def get_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> Memory:
    memory = (
        await session.execute(
            select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        )
    ).scalar_one_or_none()
    if memory is None:
        raise NotFound("Memory not found")
    return memory


async def save_candidate(
    session: AsyncSession,
    user_id: UUID,
    candidate: Candidate,
    *,
    source_message_id: UUID | None,
    source_conversation_id: UUID | None,
) -> Memory | None:
    """Store a candidate, or update a near-duplicate. Returns None if it was dropped."""
    if candidate.type not in MEMORY_TYPES:
        return None
    sensitive = candidate.sensitivity == "sensitive"
    if sensitive and not (await consent_state(session, user_id))["sensitive_memory"]:
        return None  # sensitive information is not kept unless the user has opted in

    now = datetime.now(UTC)
    existing = await list_memories(session, user_id)
    for memory in existing:
        if (
            memory.type == candidate.type
            and similarity(text_of(memory), candidate.content) >= DEDUPE_THRESHOLD
        ):
            memory.last_confirmed_at = now
            if not sensitive and memory.sensitivity == "normal":
                memory.content = candidate.content
            await session.flush()
            return memory

    memory = Memory(
        user_id=user_id,
        type=candidate.type,
        confidence=candidate.confidence,
        sensitivity="sensitive" if sensitive else "normal",
        status="pending" if sensitive else "active",
        source_message_id=source_message_id,
        source_conversation_id=source_conversation_id,
    )
    if sensitive:
        memory.content = ""
        memory.content_encrypted = crypto.encrypt(candidate.content)
    else:
        memory.content = candidate.content
    session.add(memory)
    await session.flush()
    return memory


async def edit_memory(
    session: AsyncSession, user_id: UUID, memory_id: UUID, *, content: str | None, type_: str | None
) -> Memory:
    memory = await get_memory(session, user_id, memory_id)
    if type_ is not None:
        if type_ not in MEMORY_TYPES:
            raise AppError("Unknown memory type")
        memory.type = type_
    if content is not None:
        if memory.sensitivity == "sensitive":
            memory.content_encrypted = crypto.encrypt(content)
        else:
            memory.content = content
    memory.last_confirmed_at = datetime.now(UTC)
    await audit.record(
        session,
        "memory.update",
        user_id=user_id,
        resource_type="memory",
        resource_id=str(memory_id),
    )
    await session.flush()
    return memory


async def confirm_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> Memory:
    memory = await get_memory(session, user_id, memory_id)
    memory.status = "active"
    memory.last_confirmed_at = datetime.now(UTC)
    await session.flush()
    return memory


async def delete_memory(session: AsyncSession, user_id: UUID, memory_id: UUID) -> None:
    memory = await get_memory(session, user_id, memory_id)
    await session.delete(memory)
    await audit.record(
        session,
        "memory.delete",
        user_id=user_id,
        resource_type="memory",
        resource_id=str(memory_id),
    )


async def delete_all(session: AsyncSession, user_id: UUID) -> int:
    result = await session.execute(delete(Memory).where(Memory.user_id == user_id))
    count: int = result.rowcount  # type: ignore[attr-defined]
    await audit.record(
        session,
        "memory.delete_all",
        user_id=user_id,
        resource_type="memory",
        metadata={"count": count},
    )
    return count
