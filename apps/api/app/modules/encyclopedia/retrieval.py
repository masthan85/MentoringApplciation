"""Hybrid retrieval: full text plus vectors, fused, re-ranked, weighted by authority and freshness."""

import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.encyclopedia.rerank import Reranker, get_reranker, keywords
from app.modules.llm_gateway import LLMError, current_gateway

log = logging.getLogger(__name__)

CANDIDATES = 30
RRF_K = 60
MAX_PER_SOURCE = 3
# Vector hits must be at least this similar (cosine) to count. Full-text matches need no floor
# because they already share words with the question.
MIN_VECTOR_SIMILARITY = 0.25
AUTHORITY = {
    "official": 1.0,
    "standard": 0.95,
    "peer_reviewed": 0.9,
    "expert_authored": 0.8,
    "community": 0.5,
}
# Days until a source's freshness factor is halfway to its floor.
HALF_LIFE_DAYS = {"stable": 1825, "moderate": 730, "volatile": 180}
FRESHNESS_FLOOR = 0.5
_SAFE_WORD = re.compile(r"^[a-z0-9]+$")


@dataclass(frozen=True)
class Retrieved:
    chunk_id: UUID
    source_id: UUID
    slug: str
    title: str
    url: str | None
    publisher: str | None
    tier: str
    volatility: str
    published_date: date | None
    last_reviewed: date | None
    heading_path: str
    text: str
    score: float

    @property
    def as_of(self) -> date | None:
        return self.last_reviewed or self.published_date


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[Retrieved]
    used_vectors: bool


def freshness_factor(volatility: str, as_of: date | None, today: date | None = None) -> float:
    if as_of is None:
        return FRESHNESS_FLOOR + (1 - FRESHNESS_FLOOR) * 0.5  # unknown age: assume middling
    age = max(((today or datetime.now(UTC).date()) - as_of).days, 0)
    half = HALF_LIFE_DAYS.get(volatility, HALF_LIFE_DAYS["moderate"])
    return FRESHNESS_FLOOR + (1 - FRESHNESS_FLOOR) * math.pow(0.5, age / half)


def final_score(
    relevance: float, tier: str, volatility: str, as_of: date | None, today: date | None = None
) -> float:
    return relevance * AUTHORITY.get(tier, 0.5) * freshness_factor(volatility, as_of, today)


def or_query(query: str, limit: int = 12) -> str | None:
    """A to_tsquery string that matches any of the query's significant words."""
    words = [w for w in keywords(query) if _SAFE_WORD.match(w)][:limit]
    return " | ".join(words) if words else None


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


_FILTER = """
  s.status = 'active'
  AND (s.domain = ANY(:domains) OR s.domain = 'general')
  AND s.jurisdiction = ANY(:jurisdictions)
"""

_FTS_SQL = text(
    f"""
    SELECT c.id FROM chunks c JOIN sources s ON s.id = c.source_id
    WHERE {_FILTER} AND c.tsv @@ to_tsquery('english', :tsq)
    ORDER BY ts_rank_cd(c.tsv, to_tsquery('english', :tsq)) DESC
    LIMIT :n
    """
)
_VEC_SQL = text(
    f"""
    SELECT c.id FROM chunks c JOIN sources s ON s.id = c.source_id
    WHERE {_FILTER} AND c.embedding IS NOT NULL
      AND (c.embedding <=> CAST(:vec AS vector)) <= :max_distance
    ORDER BY c.embedding <=> CAST(:vec AS vector)
    LIMIT :n
    """
)
_DETAIL_SQL = text(
    """
    SELECT c.id AS chunk_id, c.source_id, c.heading_path, c.text,
           s.slug, s.title, s.url, s.publisher, s.authority_tier, s.volatility,
           s.published_date, s.last_reviewed
    FROM chunks c JOIN sources s ON s.id = c.source_id
    WHERE c.id = ANY(:ids)
    """
)


async def retrieve(
    session: AsyncSession,
    query: str,
    *,
    domains: list[str],
    jurisdictions: tuple[str, ...] = ("global", "GB"),
    limit: int = 6,
    reranker: Reranker | None = None,
    today: date | None = None,
) -> RetrievalResult:
    params = {
        "domains": domains or ["general"],
        "jurisdictions": list(jurisdictions),
        "n": CANDIDATES,
    }
    ranks: dict[UUID, float] = {}

    tsq = or_query(query)
    if tsq:
        for rank, row in enumerate((await session.execute(_FTS_SQL, {**params, "tsq": tsq})).all()):
            ranks[row.id] = ranks.get(row.id, 0.0) + 1 / (RRF_K + rank + 1)

    used_vectors = False
    try:
        embedded = await current_gateway().embed([query[:2000]])
        for rank, row in enumerate(
            (
                await session.execute(
                    _VEC_SQL,
                    {
                        **params,
                        "vec": _vector_literal(embedded.vectors[0]),
                        "max_distance": 1 - MIN_VECTOR_SIMILARITY,
                    },
                )
            ).all()
        ):
            ranks[row.id] = ranks.get(row.id, 0.0) + 1 / (RRF_K + rank + 1)
        used_vectors = True
    except LLMError:
        log.info("embeddings unavailable; retrieving with full text only")
    if not ranks:
        return RetrievalResult([], used_vectors)

    details = {
        row.chunk_id: row
        for row in (await session.execute(_DETAIL_SQL, {"ids": list(ranks)})).all()
    }
    ordered = sorted(details, key=lambda cid: ranks[cid], reverse=True)[:CANDIDATES]
    top_rrf = max(ranks.values())
    passages = [details[cid].text for cid in ordered]
    lexical = (reranker or get_reranker()).score(query, passages)

    scored: list[Retrieved] = []
    for cid, lex in zip(ordered, lexical, strict=True):
        row = details[cid]
        relevance = 0.6 * (ranks[cid] / top_rrf) + 0.4 * lex
        as_of = row.last_reviewed or row.published_date
        scored.append(
            Retrieved(
                chunk_id=cid,
                source_id=row.source_id,
                slug=row.slug,
                title=row.title,
                url=row.url,
                publisher=row.publisher,
                tier=row.authority_tier,
                volatility=row.volatility,
                published_date=row.published_date,
                last_reviewed=row.last_reviewed,
                heading_path=row.heading_path,
                text=row.text,
                score=final_score(relevance, row.authority_tier, row.volatility, as_of, today),
            )
        )
    scored.sort(key=lambda r: r.score, reverse=True)

    picked: list[Retrieved] = []
    per_source: dict[UUID, int] = {}
    for item in scored:
        if per_source.get(item.source_id, 0) >= MAX_PER_SOURCE:
            continue
        picked.append(item)
        per_source[item.source_id] = per_source.get(item.source_id, 0) + 1
        if len(picked) >= limit:
            break
    return RetrievalResult(picked, used_vectors)
