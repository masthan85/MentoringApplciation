import logging

from app.core.db import get_engine
from app.core.redis import get_redis
from fastapi import APIRouter, Response
from sqlalchemy import text

log = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, object]:
    """Readiness: dependencies this service needs are reachable."""
    checks: dict[str, str] = {}
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        log.warning("database readiness check failed", exc_info=True)
        checks["database"] = "unavailable"
    try:
        await get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        log.warning("redis readiness check failed", exc_info=True)
        checks["redis"] = "unavailable"
    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "not_ready", "checks": checks}
