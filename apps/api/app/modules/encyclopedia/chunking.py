"""Split a document by heading, then by paragraph, with a little overlap."""

import re
from dataclasses import dataclass

TARGET_TOKENS = 350
MAX_TOKENS = 600
OVERLAP_TOKENS = 50
_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def approx_tokens(text: str) -> int:
    return max(len(text) // 4, 1)


@dataclass(frozen=True)
class RawChunk:
    heading_path: str
    text: str


def _sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    path: list[tuple[int, str]] = []
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((" > ".join(title for _, title in path), body))
        buffer.clear()

    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            while path and path[-1][0] >= level:
                path.pop()
            path.append((level, match.group(2)))
        else:
            buffer.append(line)
    flush()
    return sections


def _split_long(paragraph: str) -> list[str]:
    if approx_tokens(paragraph) <= MAX_TOKENS:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE.split(paragraph):
        if current and approx_tokens(current + " " + sentence) > TARGET_TOKENS:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, tokens: int) -> str:
    words = text.split()
    keep = max(tokens * 3 // 4, 1)  # ~0.75 words per token
    return " ".join(words[-keep:]) if len(words) > keep else ""


def chunk_markdown(markdown: str) -> list[RawChunk]:
    chunks: list[RawChunk] = []
    for heading, body in _sections(markdown):
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
        pieces = [piece for p in paragraphs for piece in _split_long(p)]
        current: list[str] = []
        used = 0
        for piece in pieces:
            cost = approx_tokens(piece)
            if current and used + cost > TARGET_TOKENS:
                text = "\n\n".join(current)
                chunks.append(RawChunk(heading, text))
                overlap = _tail(text, OVERLAP_TOKENS)
                current = [overlap] if overlap else []
                used = approx_tokens(overlap) if overlap else 0
            current.append(piece)
            used += cost
        if current:
            text = "\n\n".join(current)
            if not chunks or chunks[-1].text != text:
                chunks.append(RawChunk(heading, text))
    return chunks
