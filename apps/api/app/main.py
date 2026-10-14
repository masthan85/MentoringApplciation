import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.errors import RateLimited, register_error_handlers
from app.core.hardening import SecurityMiddleware
from app.core.health import router as health_router
from app.core.jobs import close_pool
from app.core.logging import bind_log_context, clear_log_context, configure_logging
from app.core.redis import close_redis, get_redis, hit_rate_limit
from app.core.telemetry import setup_tracing
from app.modules.encyclopedia import jobs as _encyclopedia_jobs  # noqa: F401  (registers jobs)
from app.modules.encyclopedia.admin import router as admin_router
from app.modules.encyclopedia.router import router as sources_router
from app.modules.evaluation import service as _eval_service  # noqa: F401  (registers jobs)
from app.modules.evaluation.admin import router as evals_router
from app.modules.evaluation.router import router as feedback_router
from app.modules.fingerprint.router import router as fingerprint_router
from app.modules.goals.router import router as goals_router
from app.modules.identity.router import router as identity_router
from app.modules.memory import jobs as _memory_jobs  # noqa: F401  (registers jobs)
from app.modules.memory.router import router as memory_router
from app.modules.mentors.router import router as human_mentor_router
from app.modules.notifications import scheduler as _scheduler  # noqa: F401  (registers jobs)
from app.modules.notifications.router import router as notifications_router
from app.modules.orchestration import jobs as _orchestration_jobs  # noqa: F401  (registers jobs)
from app.modules.orchestration.router import router as conversations_router
from app.modules.persona.registry import get_registry
from app.modules.persona.router import router as persona_router
from app.modules.practice.router import router as practice_router
from app.modules.privacy.router import router as privacy_router
from app.modules.profile.router import router as profile_router
from app.modules.studio.router import router as studio_router
from app.modules.subscriptions.router import router as billing_router

log = logging.getLogger("app.request")

_UNLIMITED_PATHS = {"/healthz", "/readyz"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.service_name)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        get_registry()  # fail fast if a mentor pack is invalid
        log.info("starting", extra={"env": settings.env})
        yield
        await dispose_engine()
        await close_redis()
        await close_pool()

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

    app.add_middleware(
        SecurityMiddleware,
        max_body_bytes=settings.max_body_bytes,
        hsts=settings.env in ("staging", "production"),
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
    app.include_router(profile_router)
    app.include_router(persona_router)
    app.include_router(conversations_router)
    app.include_router(memory_router)
    app.include_router(sources_router)
    app.include_router(fingerprint_router)
    app.include_router(studio_router)
    app.include_router(feedback_router)
    app.include_router(evals_router)
    app.include_router(goals_router)
    app.include_router(notifications_router)
    app.include_router(admin_router)
    app.include_router(human_mentor_router)
    app.include_router(practice_router)
    app.include_router(privacy_router)
    app.include_router(billing_router)
    if settings.auth_mode == "dev":
        from app.modules.identity.dev import router as dev_router

        app.include_router(dev_router)
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
