"""Anthropic adapter (Messages API)."""

from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.modules.llm_gateway.config import Target
from app.modules.llm_gateway.errors import (
    InvalidRequestError,
    LLMError,
    ProviderUnavailable,
    TransientProviderError,
)
from app.modules.llm_gateway.types import (
    CompletionRequest,
    ProviderResponse,
    StreamChunk,
    Usage,
)


def map_error(exc: Exception) -> LLMError:
    if isinstance(exc, anthropic.APIConnectionError):  # includes timeouts
        return TransientProviderError(str(exc))
    if isinstance(exc, anthropic.APIStatusError):
        status = exc.status_code
        if status in (408, 409, 429) or status >= 500:
            return TransientProviderError(f"anthropic {status}")
        if status in (401, 403):
            return ProviderUnavailable(f"anthropic credentials rejected ({status})")
        return InvalidRequestError(f"anthropic {status}: {exc.message}")
    return ProviderUnavailable(f"anthropic: {type(exc).__name__}")


def _usage(raw: Any) -> Usage:
    return Usage(
        input_tokens=int(getattr(raw, "input_tokens", 0) or 0),
        output_tokens=int(getattr(raw, "output_tokens", 0) or 0),
        cached_input_tokens=int(getattr(raw, "cache_read_input_tokens", 0) or 0),
    )


def _text(message: Any) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, client: Any | None = None) -> None:
        # The gateway owns retries and fallback, so the SDK's own retries stay off.
        self._client: Any = client or anthropic.AsyncAnthropic(api_key=api_key, max_retries=0)

    def _kwargs(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": target.model,
            "max_tokens": max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.system:
            if request.cache_system:
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": request.system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                kwargs["system"] = request.system
        output_config: dict[str, Any] = {}
        if target.effort:
            output_config["effort"] = target.effort
        if request.response_schema:
            output_config["format"] = {"type": "json_schema", "schema": request.response_schema}
        if output_config:
            kwargs["output_config"] = output_config
        return kwargs

    async def complete(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> ProviderResponse:
        try:
            message = await self._client.messages.create(
                **self._kwargs(target, request, max_tokens)
            )
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            raise map_error(exc) from exc
        return ProviderResponse(
            text=_text(message), usage=_usage(message.usage), stop_reason=message.stop_reason
        )

    async def stream(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> AsyncIterator[StreamChunk]:
        try:
            async with self._client.messages.stream(
                **self._kwargs(target, request, max_tokens)
            ) as stream:
                async for piece in stream.text_stream:
                    yield StreamChunk(text=piece)
                message = await stream.get_final_message()
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            raise map_error(exc) from exc
        yield StreamChunk(
            final=ProviderResponse(
                text=_text(message), usage=_usage(message.usage), stop_reason=message.stop_reason
            )
        )

    async def embed(self, target: Target, texts: list[str]) -> tuple[list[list[float]], Usage]:
        raise InvalidRequestError("Anthropic does not provide an embeddings API")
