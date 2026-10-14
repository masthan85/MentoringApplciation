"""Database engine and session handling.

Every request-scoped session runs in one transaction and sets
``app.current_user_id`` for that transaction, which the row-level security
policies read. Code that forgets to filter by user therefore still cannot see
another user's rows.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from app.core.config import get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def set_current_user(session: AsyncSession, user_id: UUID | None) -> None:
    """Scope the open transaction to a user for row-level security."""
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id) if user_id else ""},
    )


@asynccontextmanager
async def session_scope(user_id: UUID | None = None) -> AsyncIterator[AsyncSession]:
    """One transaction, committed on success and rolled back on error."""
    async with get_sessionmaker()() as session, session.begin():
        await set_current_user(session, user_id)
        yield session
