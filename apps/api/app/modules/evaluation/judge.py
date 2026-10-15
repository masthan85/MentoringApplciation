"""LLM-as-judge for qualities that code cannot check. Full mode only."""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.llm_gateway.structured import parse_structured
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
JUDGE_PROMPT = ("eval_judge", 1)
DIMENSIONS = (
    "persona_consistency",
    "actionability",
    "context_awareness",
    "appropriateness",
    "honesty",
)
PASS_MEAN = 3.5
FAIL_BELOW = 3  # any dimension under this fails the scenario, whatever the mean

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [*DIMENSIONS, "rationale"],
    "properties": {**{d: {"type": "integer"} for d in DIMENSIONS}, "rationale": {"type": "string"}},
}


class Judgement(BaseModel):
    persona_consistency: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)
    context_awareness: int = Field(ge=1, le=5)
    appropriateness: int = Field(ge=1, le=5)
    honesty: int = Field(ge=1, le=5)
    rationale: str = ""

    @property
    def mean(self) -> float:
        return float(round(sum(getattr(self, d) for d in DIMENSIONS) / len(DIMENSIONS), 2))

    @property
    def passed(self) -> bool:
        return self.mean >= PASS_MEAN and all(getattr(self, d) >= FAIL_BELOW for d in DIMENSIONS)


async def judge_reply(
    *,
    profile: dict[str, Any],
    lens: str,
    history: list[dict[str, str]],
    message: str,
    reply: str,
    rubric: list[str],
) -> Judgement | None:
    prompt = json.dumps(
        {
            "user_profile": profile,
            "mentor_perspective": lens,
            "earlier_turns": history,
            "user_message": message,
            "mentor_reply": reply,
            "what_a_good_reply_does": rubric,
        },
        indent=1,
    )
    try:
        result = await current_gateway().complete(
            "judge",
            CompletionRequest(
                system=prompts.load(*JUDGE_PROMPT),
                messages=[Message("user", f"<case>\n{prompt}\n</case>")],
                response_schema=SCHEMA,
                tags={"purpose": "eval_judge"},
            ),
        )
    except LLMError:
        log.warning("judge unavailable", exc_info=True)
        return None
    return parse_structured(result.text, Judgement)
