"""The single entry point for model calls.

Application code names a route ("classifier", "chat_large", ...). The gateway
picks the provider and model from configuration, retries transient failures,
falls back to the next target, and records usage, latency and cost.
"""

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.modules.llm_gateway.config import GatewayConfig, Route, Target
from app.modules.llm_gateway.errors import (
    InvalidRequestError,
    LLMError,
    ProviderUnavailable,
    TransientProviderError,
)
from app.modules.llm_gateway.providers.base import LLMProvider
from app.modules.llm_gateway.types import (
    CompletionRequest,
    CompletionResult,
    EmbeddingResult,
    ProviderResponse,
    StreamEnd,
    StreamEvent,
    TextDelta,
    Usage,
)

log = logging.getLogger("app.llm")

Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class CallRecord:
    route: str
    provider: str
    model: str
    usage: Usage
    cost_usd: float | None
    latency_ms: float
    attempts: int
    tags: dict[str, str]


class CostSink(Protocol):
    def record(self, call: CallRecord) -> None: ...


class LoggingSink:
    """Default sink: one structured log line per call, with a cost warning."""

    def __init__(self, warn_usd: float = 0.25) -> None:
        self._warn_usd = warn_usd

    def record(self, call: CallRecord) -> None:
        extra = {
            "route": call.route,
            "provider": call.provider,
            "model": call.model,
            "input_tokens": call.usage.input_tokens,
            "output_tokens": call.usage.output_tokens,
            "cached_input_tokens": call.usage.cached_input_tokens,
            "cost_usd": call.cost_usd,
            "latency_ms": round(call.latency_ms, 1),
            "attempts": call.attempts,
            **{f"tag_{k}": v for k, v in call.tags.items()},
        }
        log.info("llm_call", extra=extra)
        if call.cost_usd is not None and call.cost_usd > self._warn_usd:
            log.warning("llm_call_over_budget", extra=extra)


def compute_cost(config: GatewayConfig, provider: str, model: str, usage: Usage) -> float | None:
    price = config.price_for(provider, model)
    if price is None:
        return None
    cached_rate = (
        price.cache_read_per_mtok if price.cache_read_per_mtok is not None else price.input_per_mtok
    )
    return (
        usage.input_tokens * price.input_per_mtok
        + usage.cached_input_tokens * cached_rate
        + usage.output_tokens * price.output_per_mtok
    ) / 1_000_000


class LLMGateway:
    def __init__(
        self,
        config: GatewayConfig,
        providers: dict[str, LLMProvider],
        sink: CostSink | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._config = config
        self._providers = providers
        self._sink = sink or LoggingSink()
        self._sleep = sleep

    # -- helpers ----------------------------------------------------------

    def _route(self, name: str, kind: str) -> Route:
        route = self._config.routes.get(name)
        if route is None:
            raise InvalidRequestError(f"Unknown LLM route: {name}")
        if route.kind != kind:
            raise InvalidRequestError(f"Route {name} is a {route.kind} route, not {kind}")
        return route

    def _targets(self, name: str, route: Route) -> list[tuple[Target, LLMProvider]]:
        pairs = [
            (t, self._providers[t.provider]) for t in route.targets if t.provider in self._providers
        ]
        if not pairs:
            raise ProviderUnavailable(f"No configured provider can serve route {name}")
        return pairs

    async def _backoff(self, attempt: int) -> None:
        await self._sleep(0.5 * (2**attempt) + random.uniform(0, 0.25))  # noqa: S311

    def _finish(
        self,
        name: str,
        target: Target,
        response: ProviderResponse,
        started: float,
        attempts: int,
        request: CompletionRequest,
    ) -> CompletionResult:
        latency_ms = (time.perf_counter() - started) * 1000
        cost = compute_cost(self._config, target.provider, target.model, response.usage)
        self._sink.record(
            CallRecord(
                name,
                target.provider,
                target.model,
                response.usage,
                cost,
                latency_ms,
                attempts,
                request.tags,
            )
        )
        return CompletionResult(
            text=response.text,
            route=name,
            provider=target.provider,
            model=target.model,
            usage=response.usage,
            cost_usd=cost,
            latency_ms=latency_ms,
            stop_reason=response.stop_reason,
        )

    # -- public API -------------------------------------------------------

    async def complete(self, route_name: str, request: CompletionRequest) -> CompletionResult:
        route = self._route(route_name, "chat")
        max_tokens = request.max_tokens or route.max_tokens
        last_error: LLMError | None = None
        attempts = 0
        started = time.perf_counter()
        for target, provider in self._targets(route_name, route):
            for attempt in range(route.retries + 1):
                attempts += 1
                try:
                    async with asyncio.timeout(route.timeout_s):
                        response = await provider.complete(target, request, max_tokens)
                except TimeoutError:
                    last_error = TransientProviderError(f"{target.provider} timed out")
                except TransientProviderError as exc:
                    last_error = exc
                except ProviderUnavailable as exc:
                    last_error = exc
                    break  # retrying the same target will not help
                else:
                    return self._finish(route_name, target, response, started, attempts, request)
                log.warning(
                    "llm_attempt_failed",
                    extra={
                        "route": route_name,
                        "provider": target.provider,
                        "error": str(last_error),
                    },
                )
                if attempt < route.retries:
                    await self._backoff(attempt)
        raise ProviderUnavailable(f"All targets failed for route {route_name}") from last_error

    async def stream(
        self, route_name: str, request: CompletionRequest
    ) -> AsyncIterator[StreamEvent]:
        """Stream text deltas, then a final StreamEnd. Retries and fallback apply
        only until the first token has been sent to the caller. ``timeout_s`` bounds
        each wait for the provider (first token and gaps between chunks)."""
        route = self._route(route_name, "chat")
        max_tokens = request.max_tokens or route.max_tokens
        last_error: LLMError | None = None
        attempts = 0
        started = time.perf_counter()
        for target, provider in self._targets(route_name, route):
            for attempt in range(route.retries + 1):
                attempts += 1
                emitted = False
                iterator = provider.stream(target, request, max_tokens).__aiter__()
                try:
                    while True:
                        # The timeout applies to each wait for the provider, not to the
                        # time the consumer spends handling a chunk.
                        try:
                            chunk = await asyncio.wait_for(iterator.__anext__(), route.timeout_s)
                        except StopAsyncIteration:
                            raise ProviderUnavailable(
                                f"{target.provider} stream ended without a result"
                            ) from None
                        if chunk.text:
                            emitted = True
                            yield TextDelta(chunk.text)
                        if chunk.final is not None:
                            result = self._finish(
                                route_name, target, chunk.final, started, attempts, request
                            )
                            yield StreamEnd(result)
                            return
                except TimeoutError:
                    last_error = TransientProviderError(f"{target.provider} timed out")
                except TransientProviderError as exc:
                    last_error = exc
                except ProviderUnavailable as exc:
                    last_error = exc
                    if emitted:
                        raise
                    break
                if emitted:
                    raise last_error  # cannot retry once text has reached the user
                log.warning(
                    "llm_attempt_failed",
                    extra={
                        "route": route_name,
                        "provider": target.provider,
                        "error": str(last_error),
                    },
                )
                if attempt < route.retries:
                    await self._backoff(attempt)
        raise ProviderUnavailable(f"All targets failed for route {route_name}") from last_error

    async def embed(self, texts: list[str], route_name: str = "embedding") -> EmbeddingResult:
        route = self._route(route_name, "embedding")
        last_error: LLMError | None = None
        started = time.perf_counter()
        for target, provider in self._targets(route_name, route):
            for attempt in range(route.retries + 1):
                try:
                    async with asyncio.timeout(route.timeout_s):
                        vectors, usage = await provider.embed(target, texts)
                except TimeoutError:
                    last_error = TransientProviderError(f"{target.provider} timed out")
                except TransientProviderError as exc:
                    last_error = exc
                except ProviderUnavailable as exc:
                    last_error = exc
                    break
                else:
                    cost = compute_cost(self._config, target.provider, target.model, usage)
                    self._sink.record(
                        CallRecord(
                            route_name,
                            target.provider,
                            target.model,
                            usage,
                            cost,
                            (time.perf_counter() - started) * 1000,
                            attempt + 1,
                            {},
                        )
                    )
                    return EmbeddingResult(
                        vectors, route_name, target.provider, target.model, usage, cost
                    )
                if attempt < route.retries:
                    await self._backoff(attempt)
        raise ProviderUnavailable(f"All targets failed for route {route_name}") from last_error
