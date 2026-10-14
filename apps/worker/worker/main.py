"""Arq worker entry point: ``arq worker.main.WorkerSettings``.

Jobs for later phases (memory extraction, ingestion, check-in scheduling,
evaluation runs) are registered here as they are built.
"""

import logging
from typing import Any, ClassVar

from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.jobs import run_job
from app.core.logging import configure_logging
from app.modules.encyclopedia import jobs as _encyclopedia_jobs  # noqa: F401  (registers jobs)
from app.modules.memory import jobs as _memory_jobs  # noqa: F401  (registers jobs)
from app.modules.orchestration import jobs as _orchestration_jobs  # noqa: F401  (registers jobs)
from arq import cron
from arq.connections import RedisSettings

log = logging.getLogger("worker")


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job: proves the API can enqueue and the worker can run."""
    return "pong"


async def run_job_entry(ctx: dict[str, Any], name: str, kwargs: dict[str, Any]) -> None:
    """Entry point for every job the API enqueues (see app.core.jobs)."""
    await run_job(name, **kwargs)


async def heartbeat(ctx: dict[str, Any]) -> None:
    log.info("worker heartbeat")


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings.log_level, "mentor-worker")
    log.info("worker started", extra={"env": settings.env})


async def on_shutdown(ctx: dict[str, Any]) -> None:
    await dispose_engine()
    log.info("worker stopped")


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ping, run_job_entry]
    cron_jobs: ClassVar[list[Any]] = [cron(heartbeat, minute=set(range(0, 60, 15)))]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 600
