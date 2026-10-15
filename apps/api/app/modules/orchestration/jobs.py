import logging
from uuid import UUID

from app.core.db import session_scope
from app.core.jobs import job
from app.modules.llm_gateway import CompletionRequest, Message, current_gateway
from app.modules.orchestration import service
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
SUMMARY = ("conversation_summary", 1)
KEEP_RECENT = 12
SUMMARISE_EVERY = 8


def needs_summary(total_messages: int, summarised: int) -> bool:
    return total_messages - KEEP_RECENT - summarised >= SUMMARISE_EVERY


@job("summarise_conversation")
async def summarise_conversation(*, user_id: str, conversation_id: str) -> None:
    uid, cid = UUID(user_id), UUID(conversation_id)
    async with session_scope(uid) as session:
        conversation = await service.get_conversation(session, uid, cid)
        messages = await service.list_messages(session, cid)
        older = messages[:-KEEP_RECENT]
        if not needs_summary(len(messages), conversation.summarised_message_count):
            return
        previous = conversation.rolling_summary or ""
        transcript = "\n".join(f"<{m.role}>{m.content[:1200]}</{m.role}>" for m in older[-40:])
    prompt = (
        f"<earlier_summary>{previous}</earlier_summary>\n" if previous else ""
    ) + f"<conversation>\n{transcript}\n</conversation>"
    result = await current_gateway().complete(
        "chat_small",
        CompletionRequest(
            system=prompts.load(*SUMMARY),
            messages=[Message("user", prompt)],
            max_tokens=500,
            tags={"purpose": "conversation_summary"},
        ),
    )
    async with session_scope(uid) as session:
        conversation = await service.get_conversation(session, uid, cid)
        conversation.rolling_summary = result.text.strip()
        conversation.summarised_message_count = len(older)
