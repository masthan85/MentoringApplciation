"""Provider-neutral request and result types for the LLM gateway."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    messages: Sequence[Message]
    system: str | None = None
    max_tokens: int | None = None  # defaults to the route's value
    # JSON Schema for structured output. The result's ``text`` is then valid JSON.
    response_schema: dict[str, Any] | None = None
    # Mark the system prompt as a stable prefix for provider-side caching.
    cache_system: bool = False
    tags: dict[str, str] = field(default_factory=dict)  # e.g. conversation_id, for logs


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    usage: Usage
    stop_reason: str | None = None


@dataclass(frozen=True)
class CompletionResult:
    text: str
    route: str
    provider: str
    model: str
    usage: Usage
    cost_usd: float | None
    latency_ms: float
    stop_reason: str | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    route: str
    provider: str
    model: str
    usage: Usage
    cost_usd: float | None


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class StreamEnd:
    result: CompletionResult


StreamEvent = TextDelta | StreamEnd


@dataclass(frozen=True)
class StreamChunk:
    """What providers yield while streaming: text pieces, then one final response."""

    text: str | None = None
    final: ProviderResponse | None = None
