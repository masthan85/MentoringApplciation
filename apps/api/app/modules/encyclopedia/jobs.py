from uuid import UUID

from app.core.db import session_scope
from app.core.jobs import job
from app.modules.encyclopedia.ingestion import embed_missing


@job("embed_missing_chunks")
async def embed_missing_chunks(*, source_id: str) -> None:
    async with session_scope(admin=True) as session:
        await embed_missing(session, UUID(source_id))
