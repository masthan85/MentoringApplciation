import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.core.deps import RequestCtx
from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.identity.service import consent_state
from app.modules.memory import service
from app.modules.memory.schemas import MemoryOut, MemoryPatch
from app.modules.persona.service import get_config
from app.modules.profile.service import get_or_create_profile, to_out

router = APIRouter(prefix="/v1/memories", tags=["memory"])


def _out(memory: Any) -> MemoryOut:
    return MemoryOut(**service.present(memory))


@router.get("", response_model=list[MemoryOut])
async def list_memories(
    ctx: RequestCtx,
    status: Literal["active", "pending"] | None = None,
    conversation_id: UUID | None = None,
    since: datetime | None = None,
) -> list[MemoryOut]:
    rows = await service.list_memories(
        ctx.session, ctx.user.id, status=status, conversation_id=conversation_id, since=since
    )
    return [_out(m) for m in rows]


@router.get("/export")
async def export_memories(
    ctx: RequestCtx, format: Annotated[Literal["json", "markdown"], Query()] = "json"
) -> Response:
    profile = to_out(await get_or_create_profile(ctx.session, ctx.user))
    persona = await get_config(ctx.session, ctx.user.id)
    memories = [
        _out(m).model_dump(mode="json")
        for m in await service.list_memories(ctx.session, ctx.user.id)
    ]
    document = {
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile": profile.model_dump(mode="json"),
        "persona": {"mode": persona.mode, "lens_ids": persona.lens_ids}
        if persona
        else {"mode": "auto"},
        "consents": await consent_state(ctx.session, ctx.user.id),
        "memories": memories,
    }
    await audit.record(
        ctx.session,
        "memory.export",
        user_id=ctx.user.id,
        resource_type="memory",
        metadata={"format": format},
    )
    if format == "json":
        return Response(
            json.dumps(document, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="mentor-notes.json"'},
        )
    return Response(
        _markdown(document),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mentor-notes.md"'},
    )


def _markdown(doc: dict[str, Any]) -> str:
    profile = doc["profile"]
    lines = ["# My mentor's notes", "", f"Exported {doc['exported_at']}", "", "## Profile", ""]
    for key in (
        "role_family",
        "seniority",
        "job_title",
        "years_experience",
        "goals_summary",
        "current_challenge",
    ):
        if profile.get(key) not in (None, ""):
            lines.append(f"- **{key.replace('_', ' ').capitalize()}:** {profile[key]}")
    if profile.get("stack"):
        lines.append(f"- **Stack:** {', '.join(profile['stack'])}")
    lines += ["", "## Memories", ""]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for memory in doc["memories"]:
        by_type.setdefault(memory["type"], []).append(memory)
    if not by_type:
        lines.append("Nothing remembered yet.")
    for type_, items in sorted(by_type.items()):
        lines += [f"### {type_.replace('_', ' ').capitalize()}", ""]
        for item in items:
            marker = " (sensitive)" if item["sensitivity"] == "sensitive" else ""
            lines.append(f"- {item['content']}{marker}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@router.patch("/{memory_id}", response_model=MemoryOut)
async def patch_memory(memory_id: UUID, body: MemoryPatch, ctx: RequestCtx) -> MemoryOut:
    if body.content is None and body.type is None:
        raise AppError("Nothing to change")
    memory = await service.edit_memory(
        ctx.session, ctx.user.id, memory_id, content=body.content, type_=body.type
    )
    return _out(memory)


@router.post("/{memory_id}/confirm", response_model=MemoryOut)
async def confirm(memory_id: UUID, ctx: RequestCtx) -> MemoryOut:
    return _out(await service.confirm_memory(ctx.session, ctx.user.id, memory_id))


@router.delete("/{memory_id}", status_code=204)
async def delete_one(memory_id: UUID, ctx: RequestCtx) -> Response:
    await service.delete_memory(ctx.session, ctx.user.id, memory_id)
    return Response(status_code=204)


@router.delete("", response_model=dict[str, int])
async def delete_everything(ctx: RequestCtx, all: bool = False) -> dict[str, int]:
    if not all:
        raise AppError("Pass all=true to delete every memory")
    return {"deleted": await service.delete_all(ctx.session, ctx.user.id)}
