import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.jobs import job
from app.modules.evaluation.models import EvalRun
from app.modules.evaluation.runner import run_suite


def environment() -> dict[str, Any]:
    from app.modules.llm_gateway.config import load_config
    from app.prompts import registry as prompts

    settings = get_settings()
    routes = load_config(settings.llm_routes_file).routes
    return {
        "provider_mode": settings.llm_default_provider,
        "routes": {
            name: [f"{t.provider}/{t.model}" for t in r.targets] for name, r in routes.items()
        },
        "prompts": prompts.compute_manifest(),
    }


async def create_run(session: AsyncSession, label: str, mode: str) -> EvalRun:
    run = EvalRun(label=label, mode=mode, environment=environment())
    session.add(run)
    await session.flush()
    return run


async def list_runs(session: AsyncSession, limit: int = 30) -> list[EvalRun]:
    return list(
        (
            await session.execute(select(EvalRun).order_by(EvalRun.started_at.desc()).limit(limit))
        ).scalars()
    )


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> EvalRun | None:
    return (await session.execute(select(EvalRun).where(EvalRun.id == run_id))).scalar_one_or_none()


async def execute_run(run_id: uuid.UUID, packs: list[str] | None = None) -> None:
    """Run the suite and store the outcome. Used by the worker job and the command line."""
    async with session_scope(admin=True) as session:
        run = await get_run(session, run_id)
        assert run is not None
        mode = run.mode
    try:
        summary = await run_suite(mode, packs=packs)
        status = "finished"
    except Exception as exc:
        summary = {"ok": False, "error": f"{type(exc).__name__}: {exc}", "results": []}
        status = "failed"
    async with session_scope(admin=True) as session:
        run = await get_run(session, run_id)
        assert run is not None
        run.results = summary.pop("results", [])
        run.summary = summary
        run.status = status
        run.finished_at = datetime.now(UTC)


@job("run_eval")
async def run_eval_job(*, run_id: str, packs: list[str] | None = None) -> None:
    await execute_run(uuid.UUID(run_id), packs)
