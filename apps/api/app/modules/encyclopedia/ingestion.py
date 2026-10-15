"""Document in, chunks (with embeddings where possible) out."""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.encyclopedia.chunking import approx_tokens, chunk_markdown
from app.modules.encyclopedia.models import Chunk, Source
from app.modules.encyclopedia.parsing import SourceMeta, split_front_matter, to_markdown
from app.modules.encyclopedia.sanitise import needs_human_review, sanitise
from app.modules.llm_gateway import LLMError, current_gateway

log = logging.getLogger(__name__)
EMBED_BATCH = 64
MAX_DOCUMENT_CHARS = 400_000


@dataclass(frozen=True)
class IngestReport:
    source_id: str
    slug: str
    status: str
    chunks: int
    embedded: int
    unchanged: bool
    findings: list[str]


async def _embed(texts: list[str]) -> list[list[float] | None]:
    """Embed in batches. Returns None for chunks that could not be embedded."""
    vectors: list[list[float] | None] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        try:
            result = await current_gateway().embed(batch)
            vectors.extend(result.vectors)
        except LLMError:
            log.warning("embedding unavailable; chunks stored without vectors", exc_info=True)
            vectors.extend([None] * len(batch))
    return vectors


async def ingest_document(
    session: AsyncSession,
    document: str | bytes,
    *,
    kind: Literal["markdown", "html", "pdf"] = "markdown",
    meta: SourceMeta | None = None,
    activate: bool = False,
) -> IngestReport:
    """Ingest one source. ``session`` must be an admin session (row-level security).

    New and changed sources land as drafts. ``activate=True`` is for trusted content already in the
    repository, and is ignored when the sanitiser found anything that needs a human.
    """
    if kind == "markdown":
        text_doc = document.decode() if isinstance(document, bytes) else document
        parsed_meta, body = split_front_matter(text_doc)
        meta = meta or parsed_meta
    else:
        if meta is None:
            raise ValueError("HTML and PDF documents need metadata supplied separately")
        body = to_markdown(document, kind)
    if len(body) > MAX_DOCUMENT_CHARS:
        raise ValueError("Document is too large")

    result = sanitise(body)
    flagged = needs_human_review(result.findings)
    content_hash = hashlib.sha256(
        (json.dumps(meta.model_dump(mode="json"), sort_keys=True) + result.text).encode()
    ).hexdigest()

    source = (
        await session.execute(select(Source).where(Source.slug == meta.slug))
    ).scalar_one_or_none()
    if source is not None and source.content_hash == content_hash and source.chunk_count > 0:
        return IngestReport(
            str(source.id),
            source.slug,
            source.status,
            source.chunk_count,
            0,
            True,
            list(source.review_flags),
        )

    fields = meta.model_dump()
    if source is None:
        source = Source(**fields, status="draft")
        session.add(source)
    else:
        for name, value in fields.items():
            setattr(source, name, value)
        if source.status == "active":
            source.status = "draft"  # changed content is reviewed again before it is served
    source.content_hash = content_hash
    source.review_flags = result.findings
    await session.flush()

    raw_chunks = chunk_markdown(result.text)
    await session.execute(delete(Chunk).where(Chunk.source_id == source.id))
    vectors = await _embed([f"{c.heading_path}\n{c.text}".strip() for c in raw_chunks])
    for ordinal, (raw, vector) in enumerate(zip(raw_chunks, vectors, strict=True)):
        session.add(
            Chunk(
                source_id=source.id,
                ordinal=ordinal,
                heading_path=raw.heading_path[:500],
                text=raw.text,
                token_count=approx_tokens(raw.text),
                domain=meta.domain,
                embedding=vector,
            )
        )
    source.chunk_count = len(raw_chunks)
    if activate and not flagged and raw_chunks:
        source.status = "active"
    await session.flush()
    return IngestReport(
        str(source.id),
        source.slug,
        source.status,
        len(raw_chunks),
        sum(v is not None for v in vectors),
        False,
        result.findings,
    )


async def embed_missing(session: AsyncSession, source_id: object) -> int:
    """Embed chunks that have no vector yet (for example after an embeddings outage)."""
    rows = (
        (
            await session.execute(
                select(Chunk)
                .where(Chunk.source_id == source_id, Chunk.embedding.is_(None))
                .order_by(Chunk.ordinal)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    vectors = await _embed([f"{c.heading_path}\n{c.text}".strip() for c in rows])
    done = 0
    for chunk, vector in zip(rows, vectors, strict=True):
        if vector is not None:
            chunk.embedding = vector
            done += 1
    await session.flush()
    return done
