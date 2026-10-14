"""OpenAI adapter (Chat Completions and Embeddings)."""

from collections.abc import AsyncIterator
from typing import Any

import openai
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
    if isinstance(exc, openai.APIConnectionError):  # includes timeouts
        return TransientProviderError(str(exc))
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        if status in (408, 409, 429) or status >= 500:
            return TransientProviderError(f"openai {status}")
        if status in (401, 403):
            return ProviderUnavailable(f"openai credentials rejected ({status})")
        return InvalidRequestError(f"openai {status}: {exc.message}")
    return ProviderUnavailable(f"openai: {type(exc).__name__}")


def _usage(raw: Any) -> Usage:
    if raw is None:
        return Usage()
    details = getattr(raw, "prompt_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0)
    return Usage(
        input_tokens=int(getattr(raw, "prompt_tokens", 0) or 0) - cached,
        output_tokens=int(getattr(raw, "completion_tokens", 0) or 0),
        cached_input_tokens=cached,
    )


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str | None = None, client: Any | None = None) -> None:
        self._client: Any = client or openai.AsyncOpenAI(api_key=api_key, max_retries=0)

    def _kwargs(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)
        kwargs: dict[str, Any] = {
            "model": target.model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if target.effort:
            kwargs["reasoning_effort"] = (
                target.effort if target.effort in ("low", "medium", "high") else "high"
            )
        if request.response_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": request.response_schema,
                    "strict": True,
                },
            }
        return kwargs

    async def complete(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> ProviderResponse:
        try:
            response = await self._client.chat.completions.create(
                **self._kwargs(target, request, max_tokens)
            )
        except (openai.APIConnectionError, openai.APIStatusError) as exc:
            raise map_error(exc) from exc
        choice = response.choices[0]
        return ProviderResponse(
            text=choice.message.content or "",
            usage=_usage(response.usage),
            stop_reason=choice.finish_reason,
        )

    async def stream(
        self, target: Target, request: CompletionRequest, max_tokens: int
    ) -> AsyncIterator[StreamChunk]:
        parts: list[str] = []
        usage = Usage()
        stop_reason: str | None = None
        try:
            stream = await self._client.chat.completions.create(
                **self._kwargs(target, request, max_tokens),
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = _usage(chunk.usage)
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta.content:
                        parts.append(choice.delta.content)
                        yield StreamChunk(text=choice.delta.content)
                    if choice.finish_reason:
                        stop_reason = choice.finish_reason
        except (openai.APIConnectionError, openai.APIStatusError) as exc:
            raise map_error(exc) from exc
        yield StreamChunk(
            final=ProviderResponse(text="".join(parts), usage=usage, stop_reason=stop_reason)
        )

    async def embed(self, target: Target, texts: list[str]) -> tuple[list[list[float]], Usage]:
        try:
            response = await self._client.embeddings.create(model=target.model, input=texts)
        except (openai.APIConnectionError, openai.APIStatusError) as exc:
            raise map_error(exc) from exc
        vectors = [list(item.embedding) for item in response.data]
        tokens = int(getattr(response.usage, "prompt_tokens", 0) or 0)
        return vectors, Usage(input_tokens=tokens)
