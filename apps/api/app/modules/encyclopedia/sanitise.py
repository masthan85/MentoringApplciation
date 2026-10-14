"""Treat every document as untrusted data before it can reach a prompt.

Removes what has no business in reference text (invisible characters, hidden HTML comments,
markup that could close our prompt delimiters) and reports phrases that look like instructions
to a model. A document with findings stays a draft until an admin has looked at it: a good
article about prompt injection will quote such phrases, so a human decides, not a filter.
"""

import re
from dataclasses import dataclass

_INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿]")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_SCRIPTY = re.compile(
    r"<(script|style|iframe|object|embed)\b.*?</\1\s*>", re.DOTALL | re.IGNORECASE
)
_DELIMITERS = re.compile(
    r"<(/?)(source|memory|user_profile|conversation_summary|user_document|system|assistant|user|"
    r"mentor|exchange|conversation|message|current_perspective|available_perspectives|recent_messages)\b",
    re.IGNORECASE,
)
_SUSPICIOUS = [
    (
        "override_instructions",
        r"\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|earlier|all)\b.{0,40}\b(instructions?|rules?|prompts?)\b",
    ),
    (
        "role_reassignment",
        r"\byou are now\b|\bfrom now on,? you (are|will|must)\b|\bact as (if you were )?(an? )?(unrestricted|jailbroken)",
    ),
    (
        "prompt_disclosure",
        r"\b(reveal|show|print|repeat|output)\b.{0,30}\b(system prompt|your instructions|hidden instructions)\b",
    ),
    ("concealment", r"\bdo not (tell|inform|mention to) the user\b"),
    (
        "chat_template_tokens",
        r"<\|(im_start|im_end|system|user|assistant)\|>|\[/?INST\]|###\s*(system|instruction)",
    ),
    (
        "exfiltration",
        r"\b(send|post|upload|exfiltrate)\b.{0,40}\b(conversation|memory|memories|user data|api key|credentials)\b",
    ),
]
_SUSPICIOUS_RX = [
    (name, re.compile(pattern, re.IGNORECASE | re.DOTALL)) for name, pattern in _SUSPICIOUS
]


@dataclass(frozen=True)
class SanitiseResult:
    text: str
    findings: list[str]


def sanitise(text: str) -> SanitiseResult:
    findings: list[str] = []
    cleaned = _INVISIBLE.sub("", text)
    if cleaned != text:
        findings.append("invisible_characters_removed")
    without_comments = _COMMENT.sub("", cleaned)
    if without_comments != cleaned:
        findings.append("html_comment_removed")
    without_scripts = _SCRIPTY.sub("", without_comments)
    if without_scripts != without_comments:
        findings.append("active_markup_removed")
    # Escape the opening bracket so a document can never close or fake one of our delimiters.
    escaped = _DELIMITERS.sub(lambda m: f"&lt;{m.group(1)}{m.group(2)}", without_scripts)
    if escaped != without_scripts:
        findings.append("prompt_delimiter_escaped")
    for name, pattern in _SUSPICIOUS_RX:
        if pattern.search(escaped):
            findings.append(f"suspicious:{name}")
    return SanitiseResult(escaped, findings)


def needs_human_review(findings: list[str]) -> bool:
    """Cosmetic clean-up is fine; anything that reads like an instruction is not."""
    return any(
        f.startswith("suspicious:") or f in ("prompt_delimiter_escaped", "active_markup_removed")
        for f in findings
    )
