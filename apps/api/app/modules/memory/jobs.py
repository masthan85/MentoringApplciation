import logging
from uuid import UUID

from sqlalchemy import select

from app.core.db import session_scope
from app.core.jobs import job
from app.modules.memory import service
from app.modules.memory.extraction import extract_candidates
from app.modules.orchestration.models import Message

log = logging.getLogger(__name__)


@job("extract_memories")
async def extract_memories(
    *, user_id: str, conversation_id: str, user_message_id: str, assistant_message_id: str
) -> None:
    uid = UUID(user_id)
    async with session_scope(uid) as session:
        rows = (
            (
                await session.execute(
                    select(Message).where(
                        Message.id.in_([UUID(user_message_id), UUID(assistant_message_id)])
                    )
                )
            )
            .scalars()
            .all()
        )
    by_role = {m.role: m for m in rows}
    user_msg, assistant_msg = by_role.get("user"), by_role.get("assistant")
    if user_msg is None or assistant_msg is None:
        return
    candidates = await extract_candidates(user_msg.content, assistant_msg.content)
    if not candidates:
        return
    async with session_scope(uid) as session:
        saved = 0
        for candidate in candidates:
            memory = await service.save_candidate(
                session,
                uid,
                candidate,
                source_message_id=user_msg.id,
                source_conversation_id=UUID(conversation_id),
            )
            saved += memory is not None
    log.info("memories extracted", extra={"candidates": len(candidates), "saved": saved})
