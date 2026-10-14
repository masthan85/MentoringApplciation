import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, StringConstraints

from app.core.deps import AdminCtx
from app.core.errors import NotFound
from app.core.jobs import enqueue
from app.modules.audit import service as audit
from app.modules.evaluation import service

router = APIRouter(prefix="/v1/admin/evals", tags=["admin"])


class RunIn(BaseModel):
    mode: Literal["smoke", "full"] = "smoke"
    label: Annotated[str, StringConstraints(max_length=120)] = "manual run"
    packs: list[str] | None = None


class RunOut(BaseModel):
    id: uuid.UUID
    label: str
    mode: str
    status: str
    summary: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None


class RunDetail(RunOut):
    results: list[dict[str, Any]]
    environment: dict[str, Any]


@router.get("", response_model=list[RunOut])
async def list_runs(ctx: AdminCtx) -> list[RunOut]:
    return [
        RunOut.model_validate(r, from_attributes=True) for r in await service.list_runs(ctx.session)
    ]


@router.post("", response_model=RunOut, status_code=202)
async def start_run(body: RunIn, ctx: AdminCtx, background: BackgroundTasks) -> RunOut:
    run = await service.create_run(ctx.session, body.label, body.mode)
    await audit.record(
        ctx.session,
        "eval.start",
        user_id=ctx.user.id,
        resource_type="eval_run",
        resource_id=str(run.id),
        metadata={"mode": body.mode},
    )
    out = RunOut.model_validate(run, from_attributes=True)
    # Queued after the response, once this transaction has committed, so the job can find the row.
    background.add_task(enqueue, "run_eval", run_id=str(run.id), packs=body.packs)
    return out


@router.get("/{run_id}", response_model=RunDetail)
async def read_run(run_id: uuid.UUID, ctx: AdminCtx) -> RunDetail:
    run = await service.get_run(ctx.session, run_id)
    if run is None:
        raise NotFound("Run not found")
    return RunDetail.model_validate(run, from_attributes=True)
