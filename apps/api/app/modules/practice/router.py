import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter
from pydantic import BaseModel, StringConstraints

from app.core.deps import RequestCtx
from app.modules.practice import service
from app.modules.subscriptions.entitlements import require_feature

router = APIRouter(prefix="/v1/practice", tags=["practice"])


class ScenarioOut(BaseModel):
    id: str
    title: str
    summary: str
    opening_hint: str


class StartIn(BaseModel):
    scenario_id: str
    context: Annotated[str, StringConstraints(strip_whitespace=True, max_length=600)] | None = None


class PracticeOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    scenario_id: str
    title: str
    status: str
    debrief: dict[str, Any] | None
    created_at: datetime


def _out(row: Any) -> PracticeOut:
    return PracticeOut(
        id=row.id,
        conversation_id=row.conversation_id,
        scenario_id=row.scenario_id,
        title=service.get_scenario(row.scenario_id).title,
        status=row.status,
        debrief=row.debrief,
        created_at=row.created_at,
    )


@router.get("/scenarios", response_model=list[ScenarioOut])
async def list_scenarios(ctx: RequestCtx) -> list[ScenarioOut]:
    return [
        ScenarioOut(**s.model_dump(include=set(ScenarioOut.model_fields)))
        for s in service.scenarios().values()
    ]


@router.post("", response_model=PracticeOut, status_code=201)
async def start(body: StartIn, ctx: RequestCtx) -> PracticeOut:
    await require_feature(ctx.session, ctx.user.id, "practice")
    return _out(await service.start(ctx.session, ctx.user.id, body.scenario_id, body.context))


@router.get("", response_model=list[PracticeOut])
async def list_practice(ctx: RequestCtx) -> list[PracticeOut]:
    return [_out(r) for r in await service.list_sessions(ctx.session)]


@router.post("/{practice_id}/finish", response_model=PracticeOut)
async def finish(practice_id: uuid.UUID, ctx: RequestCtx) -> PracticeOut:
    practice = await service.get(ctx.session, practice_id)
    return _out(await service.finish(ctx.session, practice))
