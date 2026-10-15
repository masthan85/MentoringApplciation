"""Admin: add, review, activate and retire sources; inspect packs. Admin role required."""

import uuid
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import select

from app.core.deps import AdminCtx
from app.core.errors import AppError, NotFound
from app.core.jobs import enqueue
from app.modules.audit import service as audit
from app.modules.encyclopedia.ingestion import ingest_document
from app.modules.encyclopedia.models import Source
from app.modules.encyclopedia.parsing import ParseError, SourceMeta
from app.modules.encyclopedia.schemas import IngestOut, SourceCreate, SourceOut, SourcePatch
from app.modules.persona.registry import get_registry

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(ctx: AdminCtx) -> list[SourceOut]:
    rows = (
        (await ctx.session.execute(select(Source).order_by(Source.updated_at.desc())))
        .scalars()
        .all()
    )
    return [SourceOut.model_validate(s) for s in rows]


@router.post("/sources", response_model=IngestOut, status_code=201)
async def create_source(body: SourceCreate, ctx: AdminCtx) -> IngestOut:
    try:
        meta = SourceMeta.model_validate(body.meta) if body.meta else None
        report = await ingest_document(ctx.session, body.document, kind=body.kind, meta=meta)
    except (ParseError, ValueError) as exc:
        raise AppError(str(exc)) from exc
    await audit.record(
        ctx.session,
        "source.ingest",
        user_id=ctx.user.id,
        resource_type="source",
        resource_id=report.source_id,
        metadata={"slug": report.slug, "findings": report.findings},
    )
    return IngestOut(**report.__dict__)


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def patch_source(source_id: uuid.UUID, body: SourcePatch, ctx: AdminCtx) -> SourceOut:
    source = (
        await ctx.session.execute(select(Source).where(Source.id == source_id))
    ).scalar_one_or_none()
    if source is None:
        raise NotFound("Source not found")
    if body.status == "active":
        if source.chunk_count == 0:
            raise AppError("This source has no content to serve")
        if source.review_flags and not body.acknowledge_flags:
            raise AppError(
                "This source was flagged when it was scanned. Read the flags, then activate it "
                "with acknowledge_flags set to true.",
                extra={"review_flags": source.review_flags},
            )
    changes = body.model_dump(exclude_unset=True, exclude={"acknowledge_flags"})
    for name, value in changes.items():
        setattr(source, name, value)
    await audit.record(
        ctx.session,
        "source.update",
        user_id=ctx.user.id,
        resource_type="source",
        resource_id=str(source_id),
        metadata={"changes": {k: str(v) for k, v in changes.items()}},
    )
    await ctx.session.flush()
    await ctx.session.refresh(source)  # picks up the server-side updated_at
    return SourceOut.model_validate(source)


@router.post("/sources/{source_id}/embed", status_code=202)
async def embed_source(source_id: uuid.UUID, ctx: AdminCtx) -> dict[str, str]:
    """Queue embedding of any chunks that do not have vectors yet."""
    await enqueue("embed_missing_chunks", source_id=str(source_id))
    return {"status": "queued"}


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(source_id: uuid.UUID, ctx: AdminCtx) -> Response:
    source = (
        await ctx.session.execute(select(Source).where(Source.id == source_id))
    ).scalar_one_or_none()
    if source is None:
        raise NotFound("Source not found")
    await ctx.session.delete(source)
    await audit.record(
        ctx.session,
        "source.delete",
        user_id=ctx.user.id,
        resource_type="source",
        resource_id=str(source_id),
        metadata={"slug": source.slug},
    )
    return Response(status_code=204)


@router.get("/packs")
async def list_packs(ctx: AdminCtx) -> list[dict[str, Any]]:
    registry = get_registry()
    return [
        {
            "id": pack.pack.id,
            "name": pack.pack.name,
            "version": pack.pack.version,
            "lenses": [
                {"id": lens.id, "name": lens.name, "version": lens.version, "domain": lens.domain}
                for lens in pack.lenses
            ],
        }
        for pack in registry.packs.values()
    ]
