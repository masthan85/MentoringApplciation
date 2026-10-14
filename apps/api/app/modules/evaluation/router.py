import uuid
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from app.core.deps import RequestCtx
from app.core.errors import AppError, NotFound
from app.modules.evaluation.models import Feedback
from app.modules.orchestration.models import Message
from app.modules.studio.models import Draft

router = APIRouter(prefix="/v1/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    kind: Literal["thumbs_up", "thumbs_down", "not_like_me", "other"]
    message_id: uuid.UUID | None = None
    draft_id: uuid.UUID | None = None
    note: Annotated[str, StringConstraints(max_length=1000)] | None = Field(default=None)


@router.post("", status_code=201, response_model=dict[str, str])
async def add_feedback(body: FeedbackIn, ctx: RequestCtx) -> dict[str, str]:
    if not (body.message_id or body.draft_id):
        raise AppError("Say which message or draft this is about")
    # Check the target is the user's own; foreign keys alone would accept someone else's id.
    if (
        body.message_id
        and not (
            await ctx.session.execute(
                select(Message.id).where(
                    Message.id == body.message_id, Message.user_id == ctx.user.id
                )
            )
        ).first()
    ):
        raise NotFound("Message not found")
    if (
        body.draft_id
        and not (
            await ctx.session.execute(
                select(Draft.id).where(Draft.id == body.draft_id, Draft.user_id == ctx.user.id)
            )
        ).first()
    ):
        raise NotFound("Draft not found")
    row = Feedback(
        user_id=ctx.user.id,
        message_id=body.message_id,
        draft_id=body.draft_id,
        kind=body.kind,
        note=body.note,
    )
    ctx.session.add(row)
    await ctx.session.flush()
    return {"id": str(row.id)}
