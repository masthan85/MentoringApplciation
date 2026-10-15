import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from app.core.deps import AdminCtx, RequestCtx
from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.audit.models import AuditEvent
from app.modules.privacy import service

router = APIRouter(tags=["privacy"])

DELETE_PHRASE = "delete my account"


class AccessEntry(BaseModel):
    at: datetime
    action: str
    by: str
    resource_type: str | None


class DeleteIn(BaseModel):
    confirm: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]


class AdminAuditEntry(BaseModel):
    at: datetime
    user_id: str | None
    actor_id: str | None
    action: str
    resource_type: str | None
    resource_id: str | None


@router.get("/v1/privacy/export")
async def export_everything(ctx: RequestCtx) -> Response:
    document = await service.export_all(ctx.session, ctx.user.id, ctx.user.email)
    await audit.record(ctx.session, "account.export", user_id=ctx.user.id, resource_type="user")
    return Response(
        content=json.dumps(document, indent=2, default=str),
        media_type="application/json",
        headers={"content-disposition": 'attachment; filename="mentor-export.json"'},
    )


@router.get("/v1/privacy/access-log", response_model=list[AccessEntry])
async def access_log(ctx: RequestCtx) -> list[AccessEntry]:
    return [
        AccessEntry(
            at=e.created_at,
            action=e.action,
            by=("you" if e.actor_id == e.user_id else "someone else"),
            resource_type=e.resource_type,
        )
        for e in await service.access_log(ctx.session, ctx.user.id)
    ]


@router.post("/v1/privacy/delete-account", status_code=204)
async def delete_account(body: DeleteIn, ctx: RequestCtx) -> Response:
    if body.confirm.lower() != DELETE_PHRASE:
        raise AppError(f'To confirm, type "{DELETE_PHRASE}"')
    await service.delete_account(ctx.session)
    return Response(status_code=204)


@router.get("/v1/admin/audit", response_model=list[AdminAuditEntry])
async def admin_audit(
    ctx: AdminCtx,
    action: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AdminAuditEntry]:
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
    if action:
        query = query.where(AuditEvent.action == action)
    rows = (await ctx.session.execute(query)).scalars()
    await audit.record(ctx.session, "admin.audit_viewed", user_id=None, actor_id=ctx.user.id)
    return [
        AdminAuditEntry(
            at=e.created_at,
            user_id=str(e.user_id) if e.user_id else None,
            actor_id=str(e.actor_id) if e.actor_id else None,
            action=e.action,
            resource_type=e.resource_type,
            resource_id=e.resource_id,
        )
        for e in rows
    ]
