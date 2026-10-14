"""Arq worker entry point: ``arq worker.main.WorkerSettings``.

Jobs for later phases (memory extraction, ingestion, check-in scheduling,
evaluation runs) are registered here as they are built.
"""

import logging
from typing import Any, ClassVar

from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.logging import configure_logging
from arq import cron
from arq.connections import RedisSettings

log = logging.getLogger("worker")


async def ping(ctx: dict[str, Any]) -> str:
    """Smoke-test job: proves the API can enqueue and the worker can run."""
    return "pong"


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
    functions: ClassVar[list[Any]] = [ping]
    cron_jobs: ClassVar[list[Any]] = [cron(heartbeat, minute=set(range(0, 60, 15)))]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 600
