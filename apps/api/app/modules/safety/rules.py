"""Deterministic safety rules. They run before any model and cannot be overridden.

Rules deliberately err towards caution on crisis language. A false positive costs
the user one gentle message; a false negative could cost much more.
"""

import re
from dataclasses import dataclass
from enum import IntEnum


class Risk(IntEnum):
    NORMAL = 0
    ADJACENT_REGULATED = 1
    PROHIBITED = 2
    CRISIS = 3


@dataclass(frozen=True)
class RuleHit:
    risk: Risk
    reason: str


def _rx(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


_CRISIS = _rx(
    r"\bkill(?:ing)? myself\b",
    r"\bend(?:ing)? my (?:own )?life\b",
    r"\btake my own life\b",
    r"\bcommit(?:ting)? suicide\b",
    r"\bsuicid(?:e|al)\b",
    r"\bwant(?:ed)? to die\b",
    r"\bdon'?t want to (?:be alive|live|wake up)\b",
    r"\bbetter off dead\b",
    r"\b(?:hurt|harm|cut)(?:ting)? myself\b",
    r"\bself[- ]?harm\b",
    r"\bno reason to (?:live|go on)\b",
    r"\b(?:going to|want to|planning to|plan to) (?:kill|hurt|shoot|stab) (?:him|her|them|someone|people|everyone)\b",
    r"\b(?:i am|i'm) (?:in danger|being abused|being attacked)\b",
)

_PROHIBITED: list[tuple[str, re.Pattern[str]]] = [
    (
        "live_interview_assistance",
        _rx(
            r"\b(?:during|while|in) (?:my|the|a) (?:actual |real |live )?(?:interview|assessment|exam|online test)\b.{0,80}\b(?:feed me|tell me what to say|whisper|secretly|without (?:them|the interviewer) (?:knowing|noticing)|listen(?:s|ing)? (?:in|to the (?:call|interview)))\b",
            r"\breal[- ]time (?:answers?|help|assistance|copilot) (?:for|during) (?:my |the )?(?:interview|assessment)\b",
            r"\b(?:cheat|cheating) (?:in|on|during) (?:my |the )?(?:interview|assessment|exam)\b",
        ),
    ),
    (
        "fake_credentials",
        _rx(
            r"\b(?:fake|forge|forged|fabricate|fabricated|make up|invent) (?:a |an |some |my |the )?(?:reference|references|testimonial|credential|credentials|certificate|qualification|degree|cv|resume|employment history|work history)\b",
            r"\b(?:pretend|claim|say) (?:i|that i) (?:have|hold|got|worked at) .{0,40}\b(?:certificate|degree|qualification|licen[cs]e|employer|company)\b",
        ),
    ),
    (
        "deception",
        _rx(
            r"\blie to (?:my|the) (?:employer|manager|boss|interviewer|recruiter|hiring manager)\b",
            r"\bdeceive (?:my|the) (?:employer|manager|interviewer|recruiter)\b",
        ),
    ),
]

_ADJACENT = _rx(
    r"\bunfair dismissal\b",
    r"\bemployment tribunal\b",
    r"\bredundanc(?:y|ies)\b",
    r"\bgrievance\b",
    r"\bdisciplinary\b",
    r"\bvisa\b",
    r"\bimmigration\b",
    r"\b(?:tax return|self[- ]assessment|capital gains)\b",
    r"\b(?:diagnos(?:is|ed)|medication|antidepressants?|therapy|panic attacks?|burn[- ]?out)\b",
    r"\b(?:mortgage|pension|invest(?:ing|ment)s?)\b",
)


def scan(text: str) -> RuleHit | None:
    """Return the most serious rule hit, or None."""
    if _CRISIS.search(text):
        return RuleHit(Risk.CRISIS, "crisis_language")
    for reason, pattern in _PROHIBITED:
        if pattern.search(text):
            return RuleHit(Risk.PROHIBITED, reason)
    if _ADJACENT.search(text):
        return RuleHit(Risk.ADJACENT_REGULATED, "regulated_topic")
    return None
