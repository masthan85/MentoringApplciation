import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.core.deps import RequestCtx
from app.modules.notifications import service

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    link: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationList(BaseModel):
    unread: int
    items: list[NotificationOut]


@router.get("", response_model=NotificationList)
async def list_notifications(ctx: RequestCtx) -> NotificationList:
    items = await service.list_notifications(ctx.session, ctx.user.id)
    return NotificationList(
        unread=await service.unread_count(ctx.session, ctx.user.id),
        items=[NotificationOut.model_validate(n) for n in items],
    )


@router.post("/read", response_model=dict[str, int])
async def read_all(ctx: RequestCtx) -> dict[str, int]:
    return {"marked": await service.mark_read(ctx.session, ctx.user.id, None)}


@router.post("/{notification_id}/read", response_model=dict[str, int])
async def read_one(notification_id: uuid.UUID, ctx: RequestCtx) -> dict[str, int]:
    return {"marked": await service.mark_read(ctx.session, ctx.user.id, notification_id)}
