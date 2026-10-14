"""Deterministic writing lint (Natural Voice, layer B).

Pure Python and fast. It looks for habits that make text read as mechanical, in context rather than
by banning words, and it reports which sentences caused a failure so a rewrite can be targeted.
It is a writing-quality aid. It says nothing about whether text "looks AI-generated", and must
never be turned into a detector score or used to evade detectors.
"""

import re
import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.modules.voice.text import (
    Sentence,
    content_words,
    mask_code,
    overlap,
    paragraphs,
    sentences,
    words,
)

CONFIG_PATH = Path(__file__).with_name("config.yaml")

# word or phrase -> weight. Sentence-initial uses count in full, mid-sentence uses at 40%.
DISCOURSE_MARKERS: dict[str, float] = {
    "furthermore": 1.0,
    "moreover": 1.0,
    "additionally": 1.0,
    "in addition": 0.8,
    "in conclusion": 1.5,
    "in summary": 1.0,
    "to summarise": 1.0,
    "to summarize": 1.0,
    "it is important to note": 1.5,
    "it's important to note": 1.5,
    "it is worth noting": 1.2,
    "it's worth noting": 1.2,
    "firstly": 0.7,
    "secondly": 0.7,
    "thirdly": 0.7,
    "lastly": 0.5,
    "overall": 0.5,
    "ultimately": 0.5,
    "indeed": 0.5,
    "thus": 0.5,
    "consequently": 0.5,
    "however": 0.3,
}
EMPTY_ADJECTIVES = (
    "robust|seamless|seamlessly|comprehensive|cutting-edge|powerful|innovative|game-changing|"
    "transformative|holistic|state-of-the-art|best-in-class|world-class|revolutionary|"
    "unparalleled|groundbreaking|synergy|synergies"
)
# Where the word is a real technical term, not padding.
ADJECTIVE_EXCEPTIONS = re.compile(
    r"robust (standard errors?|regression|statistics|estimators?|to (outliers|noise|missing))|"
    r"powerful (hypothesis )?test|comprehensive (test|coverage) suite",
    re.IGNORECASE,
)
_ADJECTIVE_RX = re.compile(rf"\b({EMPTY_ADJECTIVES})\b", re.IGNORECASE)
FORMULAIC_OPENERS = re.compile(
    r"^(?:great|good|excellent|fantastic|interesting) question\b|^certainly[,!.]|^absolutely[,!.]|"
    r"^sure[,!]|^of course[,!]|^i'?d be (?:happy|glad|delighted) to\b|^as an ai\b|"
    r"^thank you for (?:asking|sharing|reaching out)\b|^that'?s a (?:great|excellent|fantastic|really good)\b|"
    r"^what a (?:great|fascinating|wonderful)\b|^i hope this (?:email|message) finds you well\b|"
    r"^in today'?s (?:fast-paced|rapidly changing|digital)\b|^let'?s dive (?:in|into)\b|^let'?s delve\b",
    re.IGNORECASE,
)
FORMULAIC_CLOSERS = re.compile(
    r"\bi hope this helps\b|\blet me know if you (?:have|need|would like|want) (?:any|anything|more|further)\b|"
    r"\bfeel free to (?:ask|reach out|let me know)\b|\bhappy to help (?:further|with)\b|"
    r"\bdon'?t hesitate to\b|\bin conclusion\b|\bto (?:sum up|summari[sz]e)\b|\bin summary\b",
    re.IGNORECASE,
)
RESTATEMENT = re.compile(
    r"^(?:so,? )?(?:you(?:'re| are) asking|you(?:'d| would) like to know|you want to know|your question (?:is|about)|"
    r"regarding your question|you(?:'ve| have) asked)\b",
    re.IGNORECASE,
)
SUMMARY_CUES = re.compile(
    r"^(?:in (?:conclusion|summary)|to (?:sum up|summari[sz]e)|overall|all in all)\b", re.IGNORECASE
)
_BULLET = re.compile(r"^\s*(?:[-*•]\s+|\d+[.)]\s+)")
_HEADING = re.compile(r"^\s*#{1,6}\s+\S")


@lru_cache
def load_config() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text())
    return loaded


def thresholds_for(mode: str, channel: str) -> dict[str, float]:
    config = load_config()
    merged = dict(config["thresholds"])
    merged.update(config.get("mode_overrides", {}).get(mode, {}))
    merged.update(config.get("channel_overrides", {}).get(channel, {}))
    return merged


@dataclass(frozen=True)
class Signal:
    name: str
    value: float
    threshold: float
    failed: bool
    detail: str = ""


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    signal: str
    reason: str


@dataclass
class LintReport:
    signals: list[Signal] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    word_count: int = 0

    @property
    def failed(self) -> list[Signal]:
        return [s for s in self.signals if s.failed]

    @property
    def passed(self) -> bool:
        return not self.failed

    @property
    def score(self) -> float:
        return 1.0 if not self.signals else round(1 - len(self.failed) / len(self.signals), 3)

    def summary(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "failed": [s.name for s in self.failed],
            "signals": {s.name: round(s.value, 3) for s in self.signals},
            "words": self.word_count,
        }


def _density(count: float, word_count: int) -> float:
    return 100 * count / word_count if word_count else 0.0


def _marker_hits(sents: list[Sentence]) -> list[tuple[Sentence, float]]:
    hits: list[tuple[Sentence, float]] = []
    for sentence in sents:
        lowered = sentence.text.lower()
        total = 0.0
        for phrase, weight in DISCOURSE_MARKERS.items():
            for match in re.finditer(rf"\b{re.escape(phrase)}\b", lowered):
                initial = match.start() <= 2
                total += weight * (1.0 if initial else 0.4)
        if total:
            hits.append((sentence, total))
    return hits


def lint_text(
    text: str,
    *,
    channel: str = "chat",
    mode: str = "natural_professional",
    user_message: str | None = None,
    baseline_cv: float | None = None,
) -> LintReport:
    """Score ``text`` against the thresholds for this mode and channel.

    ``baseline_cv`` is the user's own sentence-length variation (from their fingerprint). It can
    only relax the variation threshold, never tighten it past the default.
    """
    config = load_config()
    th = thresholds_for(mode, channel)
    channel_cfg = config["channels"].get(channel, config["channels"]["chat"])
    masked = mask_code(text)
    sents = sentences(masked)
    word_count = len(words(masked))
    report = LintReport(word_count=word_count)
    if word_count == 0:
        return report
    style_ok = word_count >= th["min_words_for_style_signals"]

    def add(name: str, value: float, limit: float, failed: bool, detail: str = "") -> None:
        report.signals.append(Signal(name, value, limit, failed, detail))

    # 1. Discourse markers, weighted by position.
    if style_ok:
        hits = _marker_hits(sents)
        density = _density(sum(weight for _, weight in hits), word_count)
        failed = density > th["discourse_density_max"]
        add("discourse_markers", density, th["discourse_density_max"], failed)
        if failed:
            report.spans += [
                Span(s.start, s.end, "discourse_markers", "stacked transition words")
                for s, _ in hits
            ]

    # 2. Variation in sentence length.
    if len(sents) >= th["min_sentences_for_variation"] and style_ok:
        lengths = [len(s.words) for s in sents]
        mean = statistics.fmean(lengths)
        cv = statistics.pstdev(lengths) / mean if mean else 0.0
        limit = th["sentence_cv_min"]
        if baseline_cv is not None:
            limit = min(limit, max(baseline_cv * 0.6, 0.1))
        add(
            "sentence_variation",
            cv,
            limit,
            cv < limit,
            "sentences are too uniform" if cv < limit else "",
        )

    # 3. Headings and bullets against what the channel expects.
    lines = [line for line in masked.splitlines() if line.strip()]
    if len(lines) >= 4:
        headings = sum(bool(_HEADING.match(line)) for line in lines) / len(lines)
        bullets = sum(bool(_BULLET.match(line)) for line in lines) / len(lines)
        add(
            "heading_ratio",
            headings,
            channel_cfg["heading_ratio_max"],
            headings > channel_cfg["heading_ratio_max"],
        )
        add(
            "list_ratio",
            bullets,
            channel_cfg["list_ratio_max"],
            bullets > channel_cfg["list_ratio_max"],
        )

    # 4. Formulaic openers and closers.
    if sents:
        first, last = sents[0], sents[-1]
        opener = bool(FORMULAIC_OPENERS.search(first.text))
        closer = bool(FORMULAIC_CLOSERS.search(last.text))
        add("formulaic_opener", float(opener), 0, opener)
        add("formulaic_closer", float(closer), 0, closer)
        if opener:
            report.spans.append(Span(first.start, first.end, "formulaic_opener", "generic opener"))
        if closer:
            report.spans.append(Span(last.start, last.end, "formulaic_closer", "generic closer"))

    # 5. Restating the question (in the first sentence, or the second after a generic opener).
    if sents and user_message:
        question_words = content_words(user_message)
        best_shared, flagged = 0.0, None
        for candidate in sents[:2]:
            shared = (
                overlap(content_words(candidate.text), question_words)
                if len(question_words) >= 4
                else 0.0
            )
            explicit = bool(RESTATEMENT.search(candidate.text))
            short = len(candidate.words) <= 35
            echoes = (
                short
                and shared >= th["question_restatement_max"]
                and len(content_words(candidate.text)) >= 4
            )
            best_shared = max(best_shared, shared, float(explicit))
            if explicit or echoes:
                flagged = candidate
                break
        add(
            "question_restatement", best_shared, th["question_restatement_max"], flagged is not None
        )
        if flagged is not None:
            report.spans.append(
                Span(flagged.start, flagged.end, "question_restatement", "repeats the question")
            )

    # 6. A conclusion that repeats the body.
    paras = paragraphs(masked)
    if len(paras) >= 3 or len(sents) >= 6:
        tail_start, tail_end, tail_text = (
            paras[-1] if len(paras) >= 3 else (sents[-1].start, sents[-1].end, sents[-1].text)
        )
        body_start = tail_start
        body_words = content_words(masked[:body_start])
        shared = overlap(content_words(tail_text), body_words)
        cue = bool(SUMMARY_CUES.search(tail_text.strip()))
        failed = len(content_words(tail_text)) >= 6 and (
            shared >= th["redundant_conclusion_max"] or (cue and shared >= 0.5)
        )
        add("redundant_conclusion", shared, th["redundant_conclusion_max"], failed)
        if failed:
            report.spans.append(
                Span(tail_start, tail_end, "redundant_conclusion", "restates what was already said")
            )

    # 7. Empty adjectives.
    if style_ok:
        cleaned = ADJECTIVE_EXCEPTIONS.sub(lambda m: " " * len(m.group()), masked)
        found = list(_ADJECTIVE_RX.finditer(cleaned))
        density = _density(len(found), word_count)
        failed = density > th["empty_adjective_density_max"]
        add("empty_adjectives", density, th["empty_adjective_density_max"], failed)
        if failed:
            for match in found:
                owner = next((s for s in sents if s.start <= match.start() < s.end), None)
                if owner:
                    report.spans.append(
                        Span(owner.start, owner.end, "empty_adjectives", "vague praise words")
                    )

    # 8. Repeated phrases and repeated sentence openings.
    if style_ok:
        tokens = [w.lower() for w in words(masked)]
        grams: dict[tuple[str, ...], int] = {}
        for i in range(len(tokens) - 3):
            gram = tuple(tokens[i : i + 4])
            if (
                sum(
                    t
                    in {"the", "a", "of", "to", "and", "is", "in", "that", "it", "you", "for", "on"}
                    for t in gram
                )
                >= 3
            ):
                continue
            grams[gram] = grams.get(gram, 0) + 1
        repeated = [g for g, n in grams.items() if n >= 2]
        failed = len(repeated) > th["repeated_ngrams_max"]
        add("repeated_phrases", float(len(repeated)), th["repeated_ngrams_max"], failed)
        if failed:
            phrases = {" ".join(g) for g in repeated}
            seen: set[str] = set()
            for sentence in sents:
                lowered = " ".join(w.lower() for w in sentence.words)
                for phrase in phrases:
                    if phrase in lowered and phrase in seen:
                        report.spans.append(
                            Span(
                                sentence.start, sentence.end, "repeated_phrases", "repeats a phrase"
                            )
                        )
                        break
                    if phrase in lowered:
                        seen.add(phrase)
        if len(sents) >= 4:
            openings: dict[str, int] = {}
            for sentence in sents:
                key = " ".join(w.lower() for w in sentence.words[:2])
                if key:
                    openings[key] = openings.get(key, 0) + 1
            share = max(openings.values()) / len(sents)
            worst = max(openings.values())
            failed = share > th["repeated_opening_share_max"] and worst >= 3
            add("repeated_openings", share, th["repeated_opening_share_max"], failed)
            if failed:
                common = max(openings, key=lambda k: openings[k])
                report.spans += [
                    Span(s.start, s.end, "repeated_openings", "same opening as its neighbours")
                    for s in sents[1:]
                    if " ".join(w.lower() for w in s.words[:2]) == common
                ]

    # 9. Length against the channel.
    low, high = channel_cfg["target_words"]
    limit = high * th["length_tolerance"]
    add("length", float(word_count), limit, word_count > limit, f"target {low} to {high} words")

    report.spans = merge_spans(report.spans)
    return report


def merge_spans(spans: list[Span]) -> list[Span]:
    """Combine overlapping spans, keeping every reason."""
    merged: list[Span] = []
    for span in sorted(spans, key=lambda s: (s.start, s.end)):
        if merged and span.start < merged[-1].end:
            previous = merged[-1]
            reasons = (
                previous.reason
                if span.reason in previous.reason
                else f"{previous.reason}; {span.reason}"
            )
            merged[-1] = Span(previous.start, max(previous.end, span.end), previous.signal, reasons)
        else:
            merged.append(span)
    return merged


def mean_sentence_cv(text: str) -> float | None:
    sents = sentences(mask_code(text))
    if len(sents) < 4:
        return None
    lengths = [len(s.words) for s in sents]
    mean = statistics.fmean(lengths)
    return statistics.pstdev(lengths) / mean if mean else None


__all__ = [
    "LintReport",
    "Signal",
    "Span",
    "lint_text",
    "load_config",
    "mean_sentence_cv",
    "thresholds_for",
]
