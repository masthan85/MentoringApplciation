"""Facts that a rewrite must not change: numbers, versions, dates, URLs, code and named things.

Extraction is deterministic. If anything differs between the original and the rewrite, the rewrite
is discarded and the original is used.
"""

import re
from dataclasses import dataclass, field

_MONTHS = (
    "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    "Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`([^`\n]+)`")
_URL = re.compile(r"https?://[^\s<>\")\]]+")
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_TEXT_DATE = re.compile(
    rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?(?:,?\s+\d{{4}})?|(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?|Q[1-4]\s+\d{{4}})\b"
)
_VERSION = re.compile(r"\bv?\d+(?:\.\d+){2,3}(?:-[A-Za-z0-9.]+)?\b|\bv\d+(?:\.\d+)?\b")
_NUMBER = re.compile(r"[£$€]?\d[\d,]*(?:\.\d+)?(?:%|[kKmMbB]\b)?")
_ACRONYM = re.compile(r"\b[A-Z]{2,}[A-Za-z0-9]*\b")
_CAMEL = re.compile(r"\b[A-Za-z]*[a-z][A-Z][A-Za-z0-9]*\b")
_CAPITALISED = re.compile(r"\b[A-Z][a-z][A-Za-z0-9]*\b")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n\s*(?:[-*•]\s+|\d+[.)]\s+)?)$")
# Capitalised words that are ordinary English, so seeing them mid-sentence is not a named thing.
_COMMON = frozenset(
    [
        "I",
        "I'm",
        "I'd",
        "I'll",
        "I've",
        "The",
        "A",
        "An",
        "This",
        "That",
        "These",
        "Those",
        "It",
        "We",
        "You",
        "They",
        "He",
        "She",
        "Our",
        "Your",
        "Their",
        "My",
        "And",
        "But",
        "So",
        "If",
        "When",
        "While",
        "Because",
        "Also",
        "Then",
        "However",
        "Instead",
        "First",
        "Second",
        "Third",
        "Next",
        "Finally",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "Yes",
        "No",
        "Not",
    ]
)


@dataclass
class Facts:
    code: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    dates: set[str] = field(default_factory=set)
    versions: set[str] = field(default_factory=set)
    numbers: set[str] = field(default_factory=set)
    entities_inner: set[str] = field(default_factory=set)  # not at a sentence start
    entities_all: set[str] = field(default_factory=set)  # anywhere


def _norm_number(raw: str) -> str:
    return raw.replace(",", "").lower()


def extract_facts(text: str) -> Facts:
    facts = Facts()
    for block in _FENCE.findall(text):
        facts.code.add(block.strip())
    remainder = _FENCE.sub(" ", text)
    for inline in _INLINE.findall(remainder):
        facts.code.add(inline)
    prose = _INLINE.sub(" ", remainder)

    facts.urls = {u.rstrip(".,;:") for u in _URL.findall(prose)}
    prose = _URL.sub(" ", prose)
    facts.dates = {" ".join(d.lower().split()) for d in _ISO_DATE.findall(prose)} | {
        " ".join(m.group().lower().replace(",", "").split()) for m in _TEXT_DATE.finditer(prose)
    }
    scrubbed = _TEXT_DATE.sub(" ", _ISO_DATE.sub(" ", prose))
    facts.versions = {v.lower() for v in _VERSION.findall(scrubbed)}
    scrubbed = _VERSION.sub(" ", scrubbed)
    facts.numbers = {_norm_number(n) for n in _NUMBER.findall(scrubbed)}

    for match in _ACRONYM.finditer(prose):
        facts.entities_all.add(match.group())
        facts.entities_inner.add(match.group())
    for match in _CAMEL.finditer(prose):
        facts.entities_all.add(match.group())
        facts.entities_inner.add(match.group())
    for match in _CAPITALISED.finditer(prose):
        word = match.group()
        if word in _COMMON:
            continue
        facts.entities_all.add(word)
        if not _SENTENCE_START.search(prose[: match.start()]):
            facts.entities_inner.add(word)
    return facts


def compare(before: str, after: str) -> list[str]:
    """Differences that make a rewrite unsafe. Empty means the deterministic facts are preserved."""
    a, b = extract_facts(before), extract_facts(after)
    problems: list[str] = []
    for label in ("code", "urls", "dates", "versions", "numbers"):
        lost = getattr(a, label) - getattr(b, label)
        gained = getattr(b, label) - getattr(a, label)
        if lost:
            problems.append(f"{label} lost: {sorted(lost)[:5]}")
        if gained:
            problems.append(f"{label} added: {sorted(gained)[:5]}")
    lost_entities = a.entities_inner - b.entities_all
    new_entities = b.entities_inner - a.entities_all
    if lost_entities:
        problems.append(f"names lost: {sorted(lost_entities)[:5]}")
    if new_entities:
        problems.append(f"names added: {sorted(new_entities)[:5]}")
    return problems
