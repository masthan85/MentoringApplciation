import asyncio
import os
import time
from collections.abc import AsyncIterator, Callable
from pathlib import Path

# Settings are read once, so the test environment is fixed before the app is imported.
os.environ.update(
    {
        "ENV": "test",
        "AUTH_MODE": "dev",
        "LOG_LEVEL": "WARNING",
        "DATABASE_URL": os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://mentor_app:mentor_app@localhost:5432/mentor_test",
        ),
        "MIGRATION_DATABASE_URL": os.environ.get(
            "TEST_MIGRATION_DATABASE_URL",
            "postgresql+asyncpg://mentor:mentor@localhost:5432/mentor_test",
        ),
        "DEV_AUTH_SECRET": "test-secret-test-secret-test-secret-123456",
        "LLM_DEFAULT_PROVIDER": "mock",
        "JOBS_MODE": "inline",
    }
)

import fakeredis
import httpx
import jwt
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from app.core.config import Settings, get_settings
from app.core.db import dispose_engine
from app.core.deps import reset_verifier
from app.core.redis import set_redis
from app.main import create_app
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

API_DIR = Path(__file__).resolve().parents[1]
DEV_SECRET = os.environ["DEV_AUTH_SECRET"]


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if "db" in item.fixturenames or "client" in item.fixturenames:
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest_asyncio.fixture(scope="session")
async def owner_engine() -> AsyncIterator[AsyncEngine]:
    """Connection as the schema owner (bypasses RLS). Only for test setup."""
    engine = create_async_engine(os.environ["MIGRATION_DATABASE_URL"])
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def migrated_db(owner_engine: AsyncEngine) -> None:
    async with owner_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    # Alembic's env.py starts its own event loop, so run it off this one.
    await asyncio.to_thread(command.upgrade, cfg, "head")


@pytest_asyncio.fixture
async def db(migrated_db: None, owner_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with owner_engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, sources CASCADE"))
    yield owner_engine
    await dispose_engine()


@pytest.fixture(autouse=True)
def fake_redis() -> AsyncIterator[fakeredis.FakeAsyncRedis]:
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    set_redis(client)
    yield client  # type: ignore[misc]
    set_redis(None)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    reset_verifier()
    return create_app(settings)


@pytest_asyncio.fixture
async def client(app: FastAPI, db: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def make_token() -> Callable[..., str]:
    def _make(
        sub: str = "user-1",
        email: str | None = "ada@example.com",
        roles: list[str] | None = None,
        expires_in: int = 600,
        secret: str = DEV_SECRET,
    ) -> str:
        claims: dict[str, object] = {"sub": sub, "exp": int(time.time()) + expires_in}
        if email:
            claims["email"] = email
        if roles:
            claims["roles"] = roles
        return jwt.encode(claims, secret, algorithm="HS256")

    return _make


@pytest.fixture
def auth(make_token: Callable[..., str]) -> Callable[..., dict[str, str]]:
    def _headers(**kwargs: object) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(**kwargs)}"}

    return _headers


# ---- LLM scripting and SSE helpers (Phase 1) -------------------------------------------

import json  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Any  # noqa: E402

from app.core import jobs  # noqa: E402
from app.modules.llm_gateway import (  # noqa: E402
    CompletionRequest,
    build_gateway,
    set_gateway,
)
from app.modules.llm_gateway.providers.mock import MockProvider  # noqa: E402


@dataclass
class Script:
    """Decides what the mock model says, by looking at what it was asked."""

    chat_text: str = "Here is a considered answer to your question."
    summary_text: str = "The user is working towards a data architect role."
    classifier: dict[str, Any] = field(
        default_factory=lambda: {
            "intent": "mentoring",
            "domain": "data_engineering",
            "risk_class": "normal",
            "suggested_lens": "none",
            "lens_confidence": 0.0,
            "needs_retrieval": False,
            "time_sensitive": False,
        }
    )
    memories: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    rewrites: list[dict[str, Any]] = field(default_factory=list)
    entailed: bool = True
    entail_added: list[str] = field(default_factory=list)

    def __call__(self, request: CompletionRequest) -> str:
        props = (request.response_schema or {}).get("properties", {})
        if "risk_class" in props:
            return json.dumps(self.classifier)
        if "memories" in props:
            return json.dumps({"memories": self.memories})
        if "rewrites" in props:
            return json.dumps({"rewrites": self.rewrites})
        if "entailed" in props:
            return json.dumps(
                {"entailed": self.entailed, "missing": [], "added": self.entail_added}
            )
        if "goals_summary" in props:
            base = {
                "role_family": "unknown",
                "seniority": "unknown",
                "job_title": "",
                "years_experience": -1,
                "stack": [],
                "goals_summary": "",
                "current_challenge": "",
            }
            return json.dumps({**base, **self.profile})
        if request.tags.get("purpose") == "conversation_summary":
            return self.summary_text
        return self.chat_text

    def classify(self, **overrides: Any) -> None:
        self.classifier = {**self.classifier, **overrides}


@dataclass
class FakeLLM:
    script: Script
    provider: MockProvider

    def chat_calls(self) -> list[tuple[str, CompletionRequest]]:
        return [
            (model, req)
            for model, req in self.provider.calls
            if isinstance(req, CompletionRequest)
            and not req.response_schema
            and not req.tags.get("purpose")
        ]

    def calls_with(self, purpose: str) -> list[CompletionRequest]:
        return [
            req
            for _, req in self.provider.calls
            if isinstance(req, CompletionRequest) and req.tags.get("purpose") == purpose
        ]


@pytest.fixture
def llm(settings: Settings) -> AsyncIterator[FakeLLM]:
    script = Script()
    provider = MockProvider(name="mock", responder=script)
    gateway = build_gateway(settings.model_copy(update={"llm_default_provider": "mock"}))
    gateway._providers["mock"] = provider
    set_gateway(gateway)
    yield FakeLLM(script, provider)  # type: ignore[misc]
    set_gateway(None)


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for frame in body.strip().split("\n\n"):
        lines = frame.split("\n")
        name = next(line[7:] for line in lines if line.startswith("event: "))
        data = next(line[6:] for line in lines if line.startswith("data: "))
        events.append((name, json.loads(data)))
    return events


@pytest.fixture
def drain_jobs() -> Callable[[], Any]:
    return jobs.drain
