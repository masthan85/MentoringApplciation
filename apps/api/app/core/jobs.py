"""Background jobs.

Handlers register by name with ``@job("name")``. In ``arq`` mode ``enqueue``
pushes the job to Redis for the worker; in ``inline`` mode it runs the handler
as a background task in this process. Either way a failing job never fails the
request that queued it.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings

log = logging.getLogger("app.jobs")

JobHandler = Callable[..., Awaitable[None]]
_HANDLERS: dict[str, JobHandler] = {}
_tasks: set[asyncio.Task[None]] = set()
_pool: ArqRedis | None = None


def job(name: str) -> Callable[[JobHandler], JobHandler]:
    def register(fn: JobHandler) -> JobHandler:
        _HANDLERS[name] = fn
        return fn

    return register


async def run_job(name: str, **kwargs: Any) -> None:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise KeyError(f"Unknown job: {name}")
    await handler(**kwargs)


async def _run_guarded(name: str, kwargs: dict[str, Any]) -> None:
    try:
        await run_job(name, **kwargs)
    except Exception:
        log.exception("job failed", extra={"job": name})


async def enqueue(name: str, **kwargs: Any) -> None:
    global _pool
    if get_settings().jobs_mode == "inline":
        task = asyncio.create_task(_run_guarded(name, kwargs))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
        return
    try:
        if _pool is None:
            _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
        await _pool.enqueue_job("run_job_entry", name, kwargs)
    except Exception:
        log.exception("could not enqueue job", extra={"job": name})


async def drain() -> None:
    """Wait for inline jobs (tests)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
    _pool = None
