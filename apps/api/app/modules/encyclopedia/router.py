import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import RequestCtx
from app.core.errors import NotFound
from app.modules.encyclopedia.models import Chunk, Source
from app.modules.encyclopedia.schemas import ChunkOut, SourceDetail, SourceOut

router = APIRouter(prefix="/v1/sources", tags=["encyclopedia"])


@router.get("/{source_id}", response_model=SourceDetail)
async def read_source(source_id: uuid.UUID, ctx: RequestCtx) -> SourceDetail:
    """An active source and its text, so a user can check what an answer relied on."""
    source = (
        await ctx.session.execute(select(Source).where(Source.id == source_id))
    ).scalar_one_or_none()
    if source is None:  # row-level security hides drafts and retired sources from non-admins
        raise NotFound("Source not found")
    chunks = (
        (
            await ctx.session.execute(
                select(Chunk).where(Chunk.source_id == source_id).order_by(Chunk.ordinal)
            )
        )
        .scalars()
        .all()
    )
    return SourceDetail(
        **SourceOut.model_validate(source).model_dump(),
        chunks=[ChunkOut(heading_path=c.heading_path, text=c.text) for c in chunks],
    )
