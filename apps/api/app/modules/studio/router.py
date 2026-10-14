import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import RequestCtx
from app.modules.studio import service
from app.modules.studio.models import Draft
from app.modules.studio.schemas import DraftOut, DraftRequest, EditIn, EditOut

router = APIRouter(prefix="/v1/studio", tags=["studio"])


@router.post("/drafts", response_model=DraftOut)
async def create_draft(body: DraftRequest, ctx: RequestCtx) -> DraftOut:
    return await service.create_draft(ctx.session, ctx.user, body)


@router.get("/drafts", response_model=list[DraftOut])
async def list_drafts(ctx: RequestCtx) -> list[DraftOut]:
    rows = (
        (
            await ctx.session.execute(
                select(Draft)
                .where(Draft.user_id == ctx.user.id)
                .order_by(Draft.created_at.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )
    return [service.to_out(d) for d in rows]


@router.get("/drafts/{draft_id}", response_model=DraftOut)
async def read_draft(draft_id: uuid.UUID, ctx: RequestCtx) -> DraftOut:
    return service.to_out(await service.get_draft(ctx.session, ctx.user.id, draft_id))


@router.post("/drafts/{draft_id}/edit", response_model=EditOut)
async def save_edit(draft_id: uuid.UUID, body: EditIn, ctx: RequestCtx) -> EditOut:
    learned, reason = await service.save_edit(ctx.session, ctx.user, draft_id, body.final_text)
    return EditOut(saved=True, learned=learned, reason=reason)
