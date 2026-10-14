"""Second-stage relevance scoring. Swappable: heuristic by default, cross-encoder when installed."""

import logging
import re
from typing import Protocol

from app.core.config import get_settings

log = logging.getLogger(__name__)
_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = frozenset(
    [
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "your",
        "with",
        "this",
        "that",
        "have",
        "from",
        "they",
        "will",
        "what",
        "when",
        "how",
        "why",
        "can",
        "should",
        "would",
        "could",
        "about",
        "into",
        "over",
        "our",
        "their",
        "there",
        "any",
        "been",
        "being",
        "was",
        "were",
        "has",
        "had",
        "its",
    ]
)


def keywords(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for word in _WORD.findall(text.lower()):
        if word not in _STOP:
            seen.setdefault(word)
    return list(seen)


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]:
        """One relevance score per passage, higher is better, roughly 0 to 1."""
        ...


class HeuristicReranker:
    """Keyword coverage with a small bonus for matches in the first words of a passage."""

    def score(self, query: str, passages: list[str]) -> list[float]:
        terms = keywords(query)
        if not terms:
            return [0.0] * len(passages)
        scores = []
        for passage in passages:
            tokens = set(keywords(passage))
            head = set(keywords(passage[:200]))
            coverage = sum(t in tokens for t in terms) / len(terms)
            head_bonus = sum(t in head for t in terms) / len(terms)
            scores.append(min(0.8 * coverage + 0.2 * head_bonus, 1.0))
        return scores


class CrossEncoderReranker:
    """sentence-transformers cross-encoder. Install with ``uv sync --group rerank``."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder  # heavy import, only when selected

        self._model = CrossEncoder(model_name)

    def score(self, query: str, passages: list[str]) -> list[float]:
        import math

        raw = self._model.predict([(query, p) for p in passages])
        return [1 / (1 + math.exp(-float(x))) for x in raw]


_instance: Reranker | None = None


def get_reranker() -> Reranker:
    global _instance
    if _instance is None:
        settings = get_settings()
        if settings.reranker == "cross_encoder":
            try:
                _instance = CrossEncoderReranker(settings.reranker_model)
            except ImportError:
                log.warning("sentence-transformers is not installed; using the heuristic reranker")
        if _instance is None:
            _instance = HeuristicReranker()
    return _instance


def set_reranker(reranker: Reranker | None) -> None:
    global _instance
    _instance = reranker
