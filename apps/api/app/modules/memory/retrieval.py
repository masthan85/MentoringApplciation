"""Pick the memories worth showing the model for this message.

Ranked by type, recency and word overlap with the message, within a token budget.
Embedding similarity arrives with the Mentor Encyclopedia in Phase 2.
"""

import math
from datetime import UTC, datetime

from app.modules.memory.models import Memory
from app.modules.memory.service import text_of, tokens

TYPE_WEIGHT = {
    "commitment": 1.0,
    "goal_context": 0.9,
    "decision": 0.8,
    "improvement_area": 0.7,
    "project": 0.6,
    "preference": 0.6,
    "achievement": 0.5,
    "advice_given": 0.5,
}
MAX_MEMORIES = 12


def approx_tokens(text: str) -> int:
    return max(len(text) // 4, 1)


def rank_memories(
    memories: list[Memory], query: str, *, budget_tokens: int = 600, now: datetime | None = None
) -> list[tuple[Memory, str]]:
    now = now or datetime.now(UTC)
    query_tokens = tokens(query)
    scored: list[tuple[float, Memory, str]] = []
    for memory in memories:
        if memory.status != "active":
            continue
        text = text_of(memory)
        age_days = max((now - memory.created_at).total_seconds() / 86400, 0)
        recency = math.exp(-age_days / 90)
        overlap = 0.0
        if query_tokens:
            mem_tokens = tokens(text)
            overlap = len(query_tokens & mem_tokens) / max(len(mem_tokens), 1)
        score = (
            0.5 * TYPE_WEIGHT.get(memory.type, 0.5) + 0.2 * recency + 0.3 * min(overlap * 2, 1.0)
        )
        scored.append((score, memory, text))
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen: list[tuple[Memory, str]] = []
    used = 0
    for _, memory, text in scored[:MAX_MEMORIES]:
        cost = approx_tokens(text) + 8
        if used + cost > budget_tokens:
            continue
        chosen.append((memory, text))
        used += cost
    return chosen
