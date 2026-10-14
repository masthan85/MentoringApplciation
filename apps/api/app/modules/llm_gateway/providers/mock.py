"""Deterministic provider for tests and key-less local development."""

import hashlib
import math
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

from app.modules.llm_gateway.config import Target
from app.modules.llm_gateway.errors import LLMError
from app.modules.llm_gateway.types import (
    CompletionRequest,
    ProviderResponse,
    StreamChunk,
    Usage,
)

Responder = Callable[[CompletionRequest], str]


def _default_responder(request: CompletionRequest) -> str:
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
