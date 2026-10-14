"""Small text utilities shared by lint, fingerprint and preservation. Offsets are preserved."""

import re
from dataclasses import dataclass

_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_DOT = chr(0x2024)  # one dot leader: looks like a full stop but is not one
_ABBREV = re.compile(r"\b(e\.g|i\.e|vs|etc|approx|cf|incl|esp|Dr|Mr|Ms|Mrs|St|No)\.", re.IGNORECASE)
_BOUNDARY = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(\[`])|\n+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*|\d+(?:[.,]\d+)*")
_STOP = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "you",
        "your",
        "i",
        "we",
        "they",
        "he",
        "she",
        "them",
        "our",
        "their",
        "not",
        "no",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "will",
        "would",
        "can",
        "could",
        "should",
        "may",
        "might",
        "so",
        "than",
        "then",
        "there",
        "here",
        "which",
        "who",
        "what",
        "when",
        "how",
        "why",
    ]
)


def mask_code(text: str) -> str:
    """Replace code with spaces of the same length, so offsets still line up with the original."""
    masked = _FENCE.sub(lambda m: " " * len(m.group()), text)
    return _INLINE_CODE.sub(lambda m: " " * len(m.group()), masked)


def _mask_abbreviations(text: str) -> str:
    # Same-length swap of the dot, so "e.g. Spark" does not look like a sentence end.
    return _ABBREV.sub(lambda m: m.group()[:-1] + _DOT, text)


@dataclass(frozen=True)
class Sentence:
    start: int
    end: int
    text: str

    @property
    def words(self) -> list[str]:
        return words(self.text)


def sentences(text: str) -> list[Sentence]:
    """Sentences (and list items) with their offsets in ``text``. Code should be masked first."""
    probe = _mask_abbreviations(text)
    result: list[Sentence] = []
    start = 0
    for match in _BOUNDARY.finditer(probe):
        _add(result, text, start, match.start())
        start = match.end()
    _add(result, text, start, len(text))
    return result


def _add(result: list[Sentence], text: str, start: int, end: int) -> None:
    piece = text[start:end]
    stripped = piece.strip()
    if not stripped or not any(c.isalnum() for c in stripped):
        return
    offset = start + (len(piece) - len(piece.lstrip()))
    result.append(Sentence(offset, offset + len(stripped), stripped))


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def content_words(text: str) -> list[str]:
    return [w.lower() for w in words(text) if w.lower() not in _STOP and len(w) > 2]


def paragraphs(text: str) -> list[tuple[int, int, str]]:
    result = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, re.DOTALL):
        result.append((match.start(), match.end(), match.group()))
    return result


def overlap(a: list[str], b: list[str]) -> float:
    """Share of the shorter word set found in the other (0 to 1)."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))
