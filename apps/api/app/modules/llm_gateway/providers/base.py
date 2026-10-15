from collections.abc import AsyncIterator
from typing import Protocol

from app.modules.llm_gateway.config import Target
from app.modules.llm_gateway.types import (
    CompletionRequest,
    ProviderResponse,
    StreamChunk,
    Usage,
)


class LLMProvider(Protocol):
    """One vendor behind the gateway. Implementations map vendor errors to the
    gateway's error types and never leak SDK objects to callers."""

    name: str

    async def complete(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> ProviderResponse: ...

    def stream(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> AsyncIterator[StreamChunk]: ...

    async def embed(self, target: Target, texts: list[str]) -> tuple[list[list[float]], Usage]: ...
