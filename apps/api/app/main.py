import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.errors import RateLimited, register_error_handlers
from app.core.health import router as health_router
from app.core.logging import bind_log_context, clear_log_context, configure_logging
from app.core.redis import close_redis, get_redis, hit_rate_limit
from app.core.telemetry import setup_tracing
from app.modules.identity.router import router as identity_router
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

log = logging.getLogger("app.request")

_UNLIMITED_PATHS = {"/healthz", "/readyz"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.service_name)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info("starting", extra={"env": settings.env})
        yield
        await dispose_engine()
        await close_redis()

    app = FastAPI(
        title="Adaptive AI Mentoring Platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        clear_log_context()
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        bind_log_context(request_id=request_id)
        started = time.perf_counter()

        response: Response
        if request.url.path not in _UNLIMITED_PATHS and await _ip_limited(request, settings):
            from app.core.errors import _problem  # local import: private helper

            response = _problem(429, RateLimited.code, "Too many requests", request)
        else:
            response = await call_next(request)

        response.headers["x-request-id"] = request_id
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("referrer-policy", "no-referrer")
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(identity_router)
    setup_tracing(app, settings)
    return app


async def _ip_limited(request: Request, settings: Settings) -> bool:
    client = request.client.host if request.client else "unknown"
    try:
        allowed, _ = await hit_rate_limit(get_redis(), f"ip:{client}", settings.rate_limit_per_ip)
    except Exception:
        log.warning("rate limiter unavailable", exc_info=True)
        return False
    return not allowed
