import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import RequestCtx
from app.modules.orchestration import service
from app.modules.orchestration.pipeline import run_turn
from app.modules.persona.registry import PackRegistry, get_registry

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])
Registry = Annotated[PackRegistry, Depends(get_registry)]


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    persona: dict[str, Any] | None = None


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class ConversationCreate(BaseModel):
    kind: Literal["onboarding", "mentoring"] = "mentoring"
    title: str | None = Field(default=None, max_length=200)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


@router.post("", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationCreate, ctx: RequestCtx) -> ConversationOut:
    conversation = await service.create_conversation(
        ctx.session, ctx.user.id, body.kind, body.title
    )
    return ConversationOut.model_validate(conversation)


@router.get("", response_model=list[ConversationOut])
async def list_conversations(ctx: RequestCtx) -> list[ConversationOut]:
    return [
        ConversationOut.model_validate(c)
        for c in await service.list_conversations(ctx.session, ctx.user.id)
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def read_conversation(conversation_id: uuid.UUID, ctx: RequestCtx) -> ConversationDetail:
    conversation = await service.get_conversation(ctx.session, ctx.user.id, conversation_id)
    messages = await service.list_messages(ctx.session, conversation_id)
    return ConversationDetail(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                persona=(m.meta or {}).get("persona_snapshot") if m.role == "assistant" else None,
            )
            for m in messages
        ],
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, ctx: RequestCtx) -> Response:
    await service.delete_conversation(ctx.session, ctx.user.id, conversation_id)
    return Response(status_code=204)


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID, body: MessageCreate, ctx: RequestCtx, registry: Registry
) -> StreamingResponse:
    # Checked here so that a bad id is a proper 404, not a broken stream.
    await service.get_conversation(ctx.session, ctx.user.id, conversation_id)
    return StreamingResponse(
        run_turn(
            user_id=ctx.user.id,
            conversation_id=conversation_id,
            text=body.content,
            registry=registry,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
