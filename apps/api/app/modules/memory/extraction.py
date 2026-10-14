"""Ask a small model for memory candidates from one exchange."""

from typing import Literal

from pydantic import BaseModel, Field

from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.llm_gateway.structured import parse_structured
from app.modules.memory.models import MEMORY_TYPES
from app.modules.memory.service import Candidate
from app.prompts import registry as prompts

PROMPT = ("memory_extraction", 1)
MIN_CONFIDENCE = 0.6

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["memories"],
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "content", "confidence", "sensitivity"],
                "properties": {
                    "type": {"type": "string", "enum": list(MEMORY_TYPES)},
                    "content": {"type": "string"},
                    "confidence": {"type": "number"},
                    "sensitivity": {"type": "string", "enum": ["normal", "sensitive"]},
                },
            },
        }
    },
}


class _Item(BaseModel):
    type: str
    content: str = Field(min_length=1)
    confidence: float
    sensitivity: Literal["normal", "sensitive"] = "normal"


class _Result(BaseModel):
    memories: list[_Item]


async def extract_candidates(
    user_text: str, assistant_text: str, *, limit: int = 5
) -> list[Candidate]:
    prompt = f"<exchange>\n<user>{user_text}</user>\n<mentor>{assistant_text}</mentor>\n</exchange>"
    try:
        result = await current_gateway().complete(
            "classifier",
            CompletionRequest(
                system=prompts.load(*PROMPT),
                messages=[Message("user", prompt)],
                response_schema=SCHEMA,
                tags={"purpose": "memory_extraction"},
            ),
        )
    except LLMError:
        return []
    parsed = parse_structured(result.text, _Result)
    if parsed is None:
        return []
    candidates = []
    for item in parsed.memories[:limit]:
        content = " ".join(item.content.split())
        if item.type not in MEMORY_TYPES or item.confidence < MIN_CONFIDENCE:
            continue
        if not 5 <= len(content) <= 300:
            continue
        candidates.append(
            Candidate(item.type, content, min(item.confidence, 1.0), item.sensitivity)
        )
    return candidates
