import asyncio
import os

from alembic import context
from app.core.db import Base
from app.modules.audit import models as _audit  # noqa: F401
from app.modules.identity import models as _identity  # noqa: F401
from sqlalchemy.ext.asyncio import create_async_engine

target_metadata = Base.metadata


def _url() -> str:
    # Read directly so migrations do not depend on auth or LLM settings.
    return os.environ.get(
        "MIGRATION_DATABASE_URL", "postgresql+asyncpg://mentor:mentor@localhost:5432/mentor"
    )


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
