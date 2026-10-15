"""Stylometric features from text the user wrote. No model involved."""

import re
import statistics
from typing import Any

from app.modules.voice.text import mask_code, paragraphs, sentences, words

MIN_WORDS_FOR_FEATURES = 120
MIN_WORDS_FOR_MTLD = 50
MIN_WORDS_TO_SCORE = 50  # a single draft can be compared with a profile from fewer words

_CONTRACTION = re.compile(
    r"\b\w+(?:n't|'re|'ve|'ll|'d|'m)\b|\b(?:it|that|there|here|what|let|he|she|who)'s\b",
    re.IGNORECASE,
)
_PASSIVE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|get|gets|got)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b", re.IGNORECASE
)
_HEDGES = re.compile(
    r"\b(?:perhaps|maybe|might|could|possibly|probably|seems?|appears?|somewhat|arguably|generally|typically|likely|"
    r"i think|i believe|i guess|sort of|kind of|tend to|tends to)\b",
    re.IGNORECASE,
)
_FIRST_PERSON = re.compile(
    r"\b(?:i|i'm|i've|i'd|i'll|me|my|mine|myself|we|we're|we've|our|us)\b", re.IGNORECASE
)
_TECH = re.compile(r"^(?:[A-Z]{2,}[A-Za-z0-9]*|[a-z]+[A-Z][A-Za-z0-9]*|\w*\d\w*|\w+_\w+)$")
_TECH_WORDS = frozenset(
    [
        "sql",
        "api",
        "dbt",
        "spark",
        "kafka",
        "airflow",
        "snowflake",
        "databricks",
        "python",
        "docker",
        "kubernetes",
        "pipeline",
        "schema",
        "lakehouse",
        "warehouse",
        "etl",
        "elt",
        "cdc",
        "idempotent",
        "latency",
        "throughput",
        "partition",
        "index",
        "query",
        "dataset",
        "model",
        "embedding",
        "vector",
        "prompt",
        "token",
        "inference",
    ]
)
_BULLET = re.compile(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)")

# (British stem, American stem, suffixes that make it the same word). Only spellings that differ in
# every context are listed: "program" and "license" are also British, and "emphasis" is the same in both.
_VERB = "(?:e|es|ed|ing|ation|ations|er|ers|able)"
_OUR = "(?:s|ed|ing|ful|ite|ites)?"
_NOUN = "(?:s|d)?"
_SPELLINGS: list[tuple[str, str, str]] = [
    *[
        (f"{b}is", f"{a}iz", _VERB)
        for b, a in [
            ("organ", "organ"),
            ("optim", "optim"),
            ("priorit", "priorit"),
            ("summar", "summar"),
            ("recogn", "recogn"),
            ("real", "real"),
            ("minim", "minim"),
            ("maxim", "maxim"),
            ("standard", "standard"),
            ("util", "util"),
            ("normal", "normal"),
            ("visual", "visual"),
            ("custom", "custom"),
            ("categor", "categor"),
            ("final", "final"),
            ("initial", "initial"),
            ("general", "general"),
            ("sanit", "sanit"),
            ("synchron", "synchron"),
            ("author", "author"),
            ("apolog", "apolog"),
            ("special", "special"),
        ]
    ],
    ("analys", "analyz", "(?:e|es|ed|ing)"),
    *[
        (b, a, _OUR)
        for b, a in [
            ("colour", "color"),
            ("behaviour", "behavior"),
            ("favour", "favor"),
            ("honour", "honor"),
            ("neighbour", "neighbor"),
            ("flavour", "flavor"),
            ("labour", "labor"),
        ]
    ],
    *[
        (b, a, _NOUN)
        for b, a in [
            ("centre", "center"),
            ("metre", "meter"),
            ("litre", "liter"),
            ("fibre", "fiber"),
            ("defence", "defense"),
            ("catalogue", "catalog"),
            ("grey", "gray"),
        ]
    ],
    ("travelling", "traveling", ""),
    ("modelling", "modeling", ""),
    ("labelled", "labeled", ""),
    ("cancelled", "canceled", ""),
    ("ageing", "aging", ""),
]
_STEM_UK = [
    (re.compile(rf"\b{b}{suffix}\b", re.IGNORECASE), re.compile(rf"\b{a}{suffix}\b", re.IGNORECASE))
    for b, a, suffix in _SPELLINGS
]


def mtld(tokens: list[str], threshold: float = 0.72) -> float | None:
    """Measure of Textual Lexical Diversity: mean length of runs that keep a type-token ratio above 0.72."""
    if len(tokens) < MIN_WORDS_FOR_MTLD:
        return None

    def one_pass(seq: list[str]) -> float:
        factors, types, count = 0.0, set(), 0
        for token in seq:
            count += 1
            types.add(token)
            if len(types) / count <= threshold:
                factors += 1
                types, count = set(), 0
        if count:
            ttr = len(types) / count
            factors += (1 - ttr) / (1 - threshold) if ttr < 1 else 0
        return len(seq) / factors if factors else float(len(seq))

    return (one_pass(tokens) + one_pass(list(reversed(tokens)))) / 2


def compute_features(text: str, min_words: int = MIN_WORDS_FOR_FEATURES) -> dict[str, Any]:
    masked = mask_code(text)
    word_list = words(masked)
    n = len(word_list)
    if n < min_words:
        return {"insufficient": True, "words": n}
    sents = sentences(masked)
    lengths = [len(s.words) for s in sents] or [n]
    mean_len = statistics.fmean(lengths)
    paras = paragraphs(masked)
    lines = [line for line in masked.splitlines() if line.strip()]
    lowered = [w.lower() for w in word_list]
    british = sum(len(uk.findall(masked)) for uk, _ in _STEM_UK)
    american = sum(len(us.findall(masked)) for _, us in _STEM_UK)
    technical = sum(1 for w in word_list if _TECH.match(w) or w.lower() in _TECH_WORDS)
    avg_word = statistics.fmean(len(w) for w in word_list)
    contractions = 100 * len(_CONTRACTION.findall(masked)) / n
    first_person = 100 * len(_FIRST_PERSON.findall(masked)) / n
    features: dict[str, Any] = {
        "insufficient": False,
        "words": n,
        "sentence_len_mean": round(mean_len, 2),
        "sentence_len_std": round(statistics.pstdev(lengths), 2),
        "sentence_cv": round(statistics.pstdev(lengths) / mean_len, 3) if mean_len else 0.0,
        "paragraph_len_mean": round(n / max(len(paras), 1), 1),
        "mtld": round(mtld(lowered) or 0.0, 1) or None,
        "contraction_rate": round(contractions, 2),
        "british_ratio": round(british / (british + american), 2)
        if british + american >= 2
        else None,
        "passive_rate": round(len(_PASSIVE.findall(masked)) / max(len(sents), 1), 3),
        "hedging_rate": round(100 * len(_HEDGES.findall(masked)) / n, 2),
        "technical_rate": round(100 * technical / n, 2),
        "first_person_rate": round(first_person, 2),
        "question_rate": round(
            sum(s.text.rstrip().endswith("?") for s in sents) / max(len(sents), 1), 3
        ),
        "list_rate": round(
            sum(bool(_BULLET.match(line)) for line in lines) / max(len(lines), 1), 3
        ),
        "avg_word_len": round(avg_word, 2),
    }
    features["formality"] = round(_formality(avg_word, contractions, first_person), 3)
    return features


def _formality(avg_word: float, contractions: float, first_person: float) -> float:
    score = 0.5 + 0.15 * (avg_word - 4.8) - 0.04 * contractions - 0.015 * first_person
    return max(0.0, min(1.0, score))


# How far apart two values must be to count as completely different, per feature.
SCALES = {
    "sentence_len_mean": 10.0,
    "sentence_cv": 0.4,
    "paragraph_len_mean": 40.0,
    "mtld": 30.0,
    "contraction_rate": 3.0,
    "passive_rate": 0.15,
    "hedging_rate": 1.5,
    "technical_rate": 8.0,
    "first_person_rate": 3.0,
    "question_rate": 0.15,
    "list_rate": 0.3,
    "formality": 0.3,
}


def similarity(sample: dict[str, Any], reference: dict[str, Any]) -> float | None:
    """1 means the same stylometric profile, 0 means as different as the scales allow."""
    if sample.get("insufficient") or reference.get("insufficient"):
        return None
    gaps = []
    for name, scale in SCALES.items():
        a, b = sample.get(name), reference.get(name)
        if a is None or b is None:
            continue
        gaps.append(min(abs(a - b) / scale, 1.0))
    return round(1 - statistics.fmean(gaps), 3) if gaps else None
