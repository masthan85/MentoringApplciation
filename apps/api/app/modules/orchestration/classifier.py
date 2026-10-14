"""Stage 1 classification: one small-model call with a strict JSON schema."""

import logging
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.llm_gateway.structured import parse_structured
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
PROMPT = ("classifier", 1)

INTENTS = [
    "mentoring",
    "technical_question",
    "decision",
    "drafting",
    "practice",
    "check_in",
    "small_talk",
    "other",
]
DOMAINS = [
    "data_engineering",
    "data_architecture",
    "ai_ml",
    "genai",
    "software_engineering",
    "leadership",
    "career",
    "security",
    "other",
]
RISKS = ["normal", "adjacent_regulated", "crisis", "prohibited"]


class _Output(BaseModel):
    intent: str
    domain: str
    risk_class: str
    suggested_lens: str
    lens_confidence: float
    needs_retrieval: bool
    time_sensitive: bool


@dataclass(frozen=True)
class Preprocess:
    intent: str = "mentoring"
    domain: str = "other"
    risk_class: Literal["normal", "adjacent_regulated", "crisis", "prohibited"] = "normal"
    suggested_lens: str | None = None
    lens_confidence: float = 0.0
    needs_retrieval: bool = False
    time_sensitive: bool = False
    source: Literal["model", "fallback", "skipped"] = "fallback"


def build_schema(lens_ids: list[str]) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "intent",
            "domain",
            "risk_class",
            "suggested_lens",
            "lens_confidence",
            "needs_retrieval",
            "time_sensitive",
        ],
        "properties": {
            "intent": {"type": "string", "enum": INTENTS},
            "domain": {"type": "string", "enum": DOMAINS},
            "risk_class": {"type": "string", "enum": RISKS},
            "suggested_lens": {"type": "string", "enum": [*lens_ids, "none"]},
            "lens_confidence": {"type": "number"},
            "needs_retrieval": {"type": "boolean"},
            "time_sensitive": {"type": "boolean"},
        },
    }


async def classify(
    text: str,
    *,
    recent: list[tuple[str, str]],
    lens_ids: list[str],
    current_lens: str,
) -> Preprocess:
    history = "\n".join(f"<{role}>{content[:400]}</{role}>" for role, content in recent[-4:])
    prompt = (
        f"<current_perspective>{current_lens}</current_perspective>\n"
        f"<available_perspectives>{', '.join(lens_ids)}</available_perspectives>\n"
        f"<recent_messages>\n{history}\n</recent_messages>\n"
        f"<message>{text[:4000]}</message>"
    )
    try:
        result = await current_gateway().complete(
            "classifier",
            CompletionRequest(
                system=prompts.load(*PROMPT),
                messages=[Message("user", prompt)],
                response_schema=build_schema(lens_ids),
                tags={"purpose": "classifier"},
            ),
        )
    except LLMError:
        log.warning("classifier unavailable; using defaults", exc_info=True)
        return Preprocess()
    parsed = parse_structured(result.text, _Output)
    if parsed is None or parsed.intent not in INTENTS or parsed.risk_class not in RISKS:
        return Preprocess()
    suggested = parsed.suggested_lens if parsed.suggested_lens in lens_ids else None
    return Preprocess(
        intent=parsed.intent,
        domain=parsed.domain if parsed.domain in DOMAINS else "other",
        risk_class=parsed.risk_class,  # type: ignore[arg-type]
        suggested_lens=suggested,
        lens_confidence=max(0.0, min(parsed.lens_confidence, 1.0)),
        needs_retrieval=parsed.needs_retrieval,
        time_sensitive=parsed.time_sensitive,
        source="model",
    )
