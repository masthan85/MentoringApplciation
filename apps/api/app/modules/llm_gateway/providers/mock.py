"""Deterministic provider for tests and key-less local development."""

import hashlib
import json
import math
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from app.modules.llm_gateway.config import Target
from app.modules.llm_gateway.errors import LLMError
from app.modules.llm_gateway.types import (
    CompletionRequest,
    ProviderResponse,
    StreamChunk,
    Usage,
)

Responder = Callable[[CompletionRequest], str]


def minimal_instance(schema: dict[str, Any]) -> Any:
    """The most neutral value that satisfies a JSON Schema (for key-less development).

    Enums resolve to "unknown" or "none" when offered, so a mock never invents facts about a user.
    """
    if "enum" in schema:
        options = schema["enum"]
        return next((o for o in ("unknown", "none") if o in options), options[0])
    kind = schema.get("type")
    if kind == "object":
        return {name: minimal_instance(sub) for name, sub in schema.get("properties", {}).items()}
    if kind == "array":
        return []
    if kind == "string":
        return ""
    if kind in ("number", "integer"):
        return -1 if kind == "integer" else 0.0
    if kind == "boolean":
        return False
    return None


def _default_responder(request: CompletionRequest) -> str:
    if request.response_schema:
        return json.dumps(minimal_instance(request.response_schema))
    last = request.messages[-1].content if request.messages else ""
    return f"[mock] {last[:200]}"


@dataclass
class MockProvider:
    name: str = "mock"
    responder: Responder = _default_responder
    embedding_dim: int = 8
    # Errors raised on successive calls before succeeding, e.g. [TransientProviderError("x")].
    failures: list[LLMError] = field(default_factory=list)
    calls: list[tuple[str, CompletionRequest | list[str]]] = field(default_factory=list)

    def _maybe_fail(self) -> None:
        if self.failures:
            raise self.failures.pop(0)

    def _respond(self, request: CompletionRequest, max_tokens: int) -> ProviderResponse:
        text = self.responder(request)
        prompt_words = sum(len(m.content.split()) for m in request.messages)
        return ProviderResponse(
            text=text,
            usage=Usage(input_tokens=prompt_words, output_tokens=len(text.split())),
            stop_reason="end_turn",
        )

    async def complete(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> ProviderResponse:
        self.calls.append((target.model, request))
        self._maybe_fail()
        return self._respond(request, max_tokens)

    async def stream(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> AsyncIterator[StreamChunk]:
        self.calls.append((target.model, request))
        self._maybe_fail()
        response = self._respond(request, max_tokens)
        words = response.text.split(" ")
        for index, word in enumerate(words):
            yield StreamChunk(text=word if index == 0 else f" {word}")
        yield StreamChunk(final=response)

    async def embed(self, target: Target, texts: list[str]) -> tuple[list[list[float]], Usage]:
        self.calls.append((target.model, texts))
        self._maybe_fail()
        return [self._vector(t) for t in texts], Usage(
            input_tokens=sum(len(t.split()) for t in texts)
        )

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        raw = [digest[i % len(digest)] - 127.5 for i in range(self.embedding_dim)]
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]
