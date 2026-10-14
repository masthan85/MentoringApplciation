from collections.abc import AsyncIterator

import pytest
from app.modules.llm_gateway.config import GatewayConfig, Price, Route, Target, load_config
from app.modules.llm_gateway.errors import (
    InvalidRequestError,
    ProviderUnavailable,
    TransientProviderError,
)
from app.modules.llm_gateway.gateway import CallRecord, LLMGateway, compute_cost
from app.modules.llm_gateway.providers.mock import MockProvider
from app.modules.llm_gateway.types import (
    CompletionRequest,
    Message,
    StreamChunk,
    StreamEnd,
    TextDelta,
    Usage,
)

REQUEST = CompletionRequest(messages=[Message("user", "hello world")])


class ListSink:
    def __init__(self) -> None:
        self.calls: list[CallRecord] = []

    def record(self, call: CallRecord) -> None:
        self.calls.append(call)


def _config(*, retries: int = 1) -> GatewayConfig:
    return GatewayConfig(
        routes={
            "chat": Route(
                targets=[Target(provider="a", model="m-a"), Target(provider="b", model="m-b")],
                retries=retries,
                max_tokens=100,
                timeout_s=1,
            ),
            "embedding": Route(kind="embedding", targets=[Target(provider="a", model="e-a")]),
        },
        pricing={"a/m-a": Price(input_per_mtok=2.0, output_per_mtok=10.0, cache_read_per_mtok=0.2)},
    )


class Harness:
    def __init__(self, a: MockProvider, b: MockProvider, retries: int = 1) -> None:
        self.sleeps: list[float] = []
        self.sink = ListSink()

        async def sleep(seconds: float) -> None:
            self.sleeps.append(seconds)

        self.gateway = LLMGateway(
            _config(retries=retries), {"a": a, "b": b}, sink=self.sink, sleep=sleep
        )


def _providers() -> tuple[MockProvider, MockProvider]:
    return MockProvider(name="a", responder=lambda r: "from a"), MockProvider(
        name="b", responder=lambda r: "from b"
    )


def test_bundled_routes_file_is_valid() -> None:
    config = load_config()
    assert {"classifier", "chat_small", "chat_large", "rewrite_small", "judge", "embedding"} <= set(
        config.routes
    )
    for name, route in config.routes.items():
        assert route.targets, name


def test_cost_with_cache_discount() -> None:
    config = _config()
    cost = compute_cost(
        config, "a", "m-a", Usage(input_tokens=1000, cached_input_tokens=1000, output_tokens=500)
    )
    assert cost == pytest.approx((1000 * 2.0 + 1000 * 0.2 + 500 * 10.0) / 1_000_000)


def test_unknown_model_cost_is_none_not_a_guess() -> None:
    assert compute_cost(_config(), "a", "other", Usage(input_tokens=10)) is None


async def test_complete_uses_first_target_and_records_usage() -> None:
    a, b = _providers()
    h = Harness(a, b)
    result = await h.gateway.complete("chat", REQUEST)
    assert (result.text, result.provider, result.model) == ("from a", "a", "m-a")
    assert result.cost_usd is not None
    assert len(h.sink.calls) == 1 and h.sink.calls[0].route == "chat"
    assert not b.calls


async def test_transient_error_is_retried_with_backoff() -> None:
    a, b = _providers()
    a.failures = [TransientProviderError("429")]
    h = Harness(a, b)
    result = await h.gateway.complete("chat", REQUEST)
    assert result.provider == "a"
    assert len(a.calls) == 2
    assert len(h.sleeps) == 1 and h.sleeps[0] >= 0.5


async def test_falls_back_when_retries_are_exhausted() -> None:
    a, b = _providers()
    a.failures = [TransientProviderError("x"), TransientProviderError("y")]
    h = Harness(a, b, retries=1)
    result = await h.gateway.complete("chat", REQUEST)
    assert (result.provider, result.text) == ("b", "from b")
    assert h.sink.calls[0].attempts == 3


async def test_credential_failure_falls_back_without_retrying() -> None:
    a, b = _providers()
    a.failures = [ProviderUnavailable("bad key")]
    h = Harness(a, b, retries=3)
    result = await h.gateway.complete("chat", REQUEST)
    assert result.provider == "b"
    assert len(a.calls) == 1
    assert h.sleeps == []


async def test_invalid_request_is_not_retried_or_failed_over() -> None:
    a, b = _providers()
    a.failures = [InvalidRequestError("too long")]
    h = Harness(a, b)
    with pytest.raises(InvalidRequestError):
        await h.gateway.complete("chat", REQUEST)
    assert not b.calls


async def test_all_targets_failing_raises_provider_unavailable() -> None:
    a, b = _providers()
    a.failures = [TransientProviderError("1"), TransientProviderError("2")]
    b.failures = [TransientProviderError("3"), TransientProviderError("4")]
    h = Harness(a, b)
    with pytest.raises(ProviderUnavailable):
        await h.gateway.complete("chat", REQUEST)


async def test_providers_without_credentials_are_skipped() -> None:
    a, _ = _providers()
    gateway = LLMGateway(_config(), {"a": a}, sink=ListSink())
    assert (await gateway.complete("chat", REQUEST)).provider == "a"
    gateway = LLMGateway(_config(), {}, sink=ListSink())
    with pytest.raises(ProviderUnavailable):
        await gateway.complete("chat", REQUEST)


async def test_unknown_route_and_wrong_kind() -> None:
    a, b = _providers()
    h = Harness(a, b)
    with pytest.raises(InvalidRequestError):
        await h.gateway.complete("nope", REQUEST)
    with pytest.raises(InvalidRequestError):
        await h.gateway.complete("embedding", REQUEST)
    with pytest.raises(InvalidRequestError):
        await h.gateway.embed(["x"], route_name="chat")


async def test_max_tokens_defaults_from_route_and_can_be_overridden() -> None:
    seen: list[int] = []

    class Spy(MockProvider):
        async def complete(self, target, request, max_tokens):  # type: ignore[no-untyped-def]
            seen.append(max_tokens)
            return await super().complete(target, request, max_tokens)

    gateway = LLMGateway(_config(), {"a": Spy(name="a")}, sink=ListSink())
    await gateway.complete("chat", REQUEST)
    await gateway.complete("chat", CompletionRequest(messages=REQUEST.messages, max_tokens=7))
    assert seen == [100, 7]


async def test_stream_yields_deltas_then_end() -> None:
    a, b = _providers()
    h = Harness(a, b)
    events = [e async for e in h.gateway.stream("chat", REQUEST)]
    assert "".join(e.text for e in events if isinstance(e, TextDelta)) == "from a"
    assert isinstance(events[-1], StreamEnd)
    assert events[-1].result.provider == "a"
    assert len(h.sink.calls) == 1


async def test_stream_falls_back_before_first_token() -> None:
    a, b = _providers()
    a.failures = [ProviderUnavailable("bad key")]
    h = Harness(a, b)
    events = [e async for e in h.gateway.stream("chat", REQUEST)]
    assert isinstance(events[-1], StreamEnd) and events[-1].result.provider == "b"


class BreaksMidStream(MockProvider):
    async def stream(self, target, request, max_tokens) -> AsyncIterator[StreamChunk]:  # type: ignore[no-untyped-def]
        yield StreamChunk(text="partial")
        raise TransientProviderError("connection reset")


async def test_stream_failure_after_first_token_is_raised_not_retried() -> None:
    _, b = _providers()
    h = Harness(BreaksMidStream(name="a"), b)
    seen: list[str] = []
    with pytest.raises(TransientProviderError):
        async for event in h.gateway.stream("chat", REQUEST):
            if isinstance(event, TextDelta):
                seen.append(event.text)
    assert seen == ["partial"]
    assert not b.calls


class NeverAnswers(MockProvider):
    async def stream(self, target, request, max_tokens) -> AsyncIterator[StreamChunk]:  # type: ignore[no-untyped-def]
        import asyncio

        await asyncio.sleep(30)
        yield StreamChunk(text="late")


async def test_stream_timeout_falls_back() -> None:
    _, b = _providers()
    h = Harness(NeverAnswers(name="a"), b, retries=0)
    events = [e async for e in h.gateway.stream("chat", REQUEST)]
    assert isinstance(events[-1], StreamEnd) and events[-1].result.provider == "b"


async def test_embeddings_route() -> None:
    a, b = _providers()
    h = Harness(a, b)
    result = await h.gateway.embed(["one", "two words"])
    assert len(result.vectors) == 2 and len(result.vectors[0]) == 8
    assert result.usage.input_tokens == 3
    # deterministic, normalised
    again = await h.gateway.embed(["one"])
    assert again.vectors[0] == result.vectors[0]
    assert sum(v * v for v in result.vectors[0]) == pytest.approx(1.0)


async def test_mock_answers_structured_requests_with_neutral_valid_json() -> None:
    import json

    from app.modules.llm_gateway.providers.mock import MockProvider as Mock
    from app.modules.orchestration.classifier import build_schema
    from app.modules.orchestration.onboarding import SCHEMA as PROFILE_SCHEMA

    provider = Mock()
    target = Target(provider="mock", model="mock-1")
    classifier = await provider.complete(
        target,
        CompletionRequest(
            messages=[Message("user", "x")], response_schema=build_schema(["a", "b"])
        ),
        100,
    )
    parsed = json.loads(classifier.text)
    assert parsed["suggested_lens"] == "none" and parsed["risk_class"] == "normal"
    profile = json.loads(
        (
            await provider.complete(
                target,
                CompletionRequest(messages=[Message("user", "x")], response_schema=PROFILE_SCHEMA),
                100,
            )
        ).text
    )
    assert profile["role_family"] == "unknown" and profile["seniority"] == "unknown"
    assert profile["stack"] == [] and profile["goals_summary"] == ""
