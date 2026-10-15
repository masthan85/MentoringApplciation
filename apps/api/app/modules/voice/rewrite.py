"""Targeted rewrite with a preservation check (Natural Voice, layer C).

Only the sentences the lint flagged are edited, by a small model told to keep every claim. The result
is accepted only if (1) numbers, versions, dates, URLs, code and names are unchanged, (2) a judge finds
no missing or added claims, and (3) the lint actually improves. Otherwise the original is returned.
Safety, crisis and refusal text is never rewritten.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.llm_gateway.structured import parse_structured
from app.modules.voice.lint import LintReport, Span, lint_text, load_config
from app.modules.voice.preservation import compare
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
REWRITE_PROMPT = ("voice_rewrite", 1)
ENTAIL_PROMPT = ("voice_entailment", 1)
MAX_SPANS = 8

REWRITE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["rewrites"],
    "properties": {
        "rewrites": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["index", "text"],
                "properties": {"index": {"type": "integer"}, "text": {"type": "string"}},
            },
        }
    },
}
ENTAIL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entailed", "missing", "added"],
    "properties": {
        "entailed": {"type": "boolean"},
        "missing": {"type": "array", "items": {"type": "string"}},
        "added": {"type": "array", "items": {"type": "string"}},
    },
}


class _Rewrites(BaseModel):
    class Item(BaseModel):
        index: int
        text: str

    rewrites: list[Item]


class _Entailment(BaseModel):
    entailed: bool
    missing: list[str] = []
    added: list[str] = []


@dataclass
class RewriteResult:
    text: str
    changed: bool
    reason: str | None = None  # why the original was kept
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] | None = None
    problems: list[str] = field(default_factory=list)


NEVER_REWRITE = {"crisis", "refusal"}


def rewrite_allowed(meta: dict[str, Any]) -> bool:
    """Fixed safety replies are never rewritten."""
    return meta.get("fixed_reply") not in NEVER_REWRITE


def apply_replacements(text: str, spans: list[Span], replacements: dict[int, str]) -> str:
    result = text
    for index in sorted(replacements, reverse=True):
        span = spans[index]
        result = result[: span.start] + replacements[index].strip() + result[span.end :]
    return result.replace("\n\n\n", "\n\n")


async def entailment_check(original: str, rewritten: str) -> tuple[bool, list[str]]:
    """Ask a small model whether any claim was lost or added. Fails closed if it cannot answer."""
    try:
        result = await current_gateway().complete(
            "classifier",
            CompletionRequest(
                system=prompts.load(*ENTAIL_PROMPT),
                messages=[
                    Message(
                        "user",
                        f"<original>\n{original}\n</original>\n<rewritten>\n{rewritten}\n</rewritten>",
                    )
                ],
                response_schema=ENTAIL_SCHEMA,
                tags={"purpose": "voice_entailment"},
            ),
        )
    except LLMError:
        return False, ["entailment check unavailable"]
    parsed = parse_structured(result.text, _Entailment)
    if parsed is None:
        return False, ["entailment check unreadable"]
    problems = [f"missing: {m}" for m in parsed.missing] + [f"added: {a}" for a in parsed.added]
    return parsed.entailed and not problems, problems


async def targeted_rewrite(
    text: str,
    report: LintReport,
    *,
    channel: str,
    mode: str,
    user_message: str | None = None,
    baseline_cv: float | None = None,
    style_note: str = "",
    allowed: bool = True,
) -> RewriteResult:
    before = report.summary()
    if not allowed:
        return RewriteResult(text, False, "rewriting is not permitted for this text", before)
    if report.passed or not report.spans:
        return RewriteResult(text, False, "nothing to fix", before)
    spans = report.spans[:MAX_SPANS]
    mode_text = load_config()["modes"].get(mode, "")
    flagged = [
        {"index": i, "problem": span.reason, "text": text[span.start : span.end]}
        for i, span in enumerate(spans)
    ]
    prompt = (
        f"<style>{mode_text} {style_note}</style>\n<channel>{channel}</channel>\n"
        f"<context>\n{text}\n</context>\n<flagged>\n{json.dumps(flagged, indent=1)}\n</flagged>"
    )
    try:
        result = await current_gateway().complete(
            "rewrite_small",
            CompletionRequest(
                system=prompts.load(*REWRITE_PROMPT),
                messages=[Message("user", prompt)],
                response_schema=REWRITE_SCHEMA,
                tags={"purpose": "voice_rewrite"},
            ),
        )
    except LLMError:
        return RewriteResult(text, False, "rewrite model unavailable", before)
    parsed = parse_structured(result.text, _Rewrites)
    if parsed is None:
        return RewriteResult(text, False, "rewrite unreadable", before)
    replacements = {
        item.index: item.text for item in parsed.rewrites if 0 <= item.index < len(spans)
    }
    if not replacements:
        return RewriteResult(text, False, "no usable rewrites", before)
    candidate = apply_replacements(text, spans, replacements)

    problems = compare(text, candidate)
    if problems:
        log.warning("rewrite rejected by preservation check", extra={"problems": problems})
        return RewriteResult(text, False, "preservation check failed", before, problems=problems)
    entailed, entail_problems = await entailment_check(text, candidate)
    if not entailed:
        log.warning("rewrite rejected by entailment check", extra={"problems": entail_problems})
        return RewriteResult(
            text, False, "entailment check failed", before, problems=entail_problems
        )
    after = lint_text(
        candidate, channel=channel, mode=mode, user_message=user_message, baseline_cv=baseline_cv
    )
    if len(after.failed) >= len(report.failed):
        return RewriteResult(
            text, False, "the rewrite did not improve the writing", before, after.summary()
        )
    return RewriteResult(candidate, True, None, before, after.summary())
