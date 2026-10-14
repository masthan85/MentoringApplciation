"""Adapter tests against fake SDK clients. No network, no keys."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import httpx2
import openai
import pytest
from app.modules.llm_gateway.config import Target
from app.modules.llm_gateway.errors import (
    InvalidRequestError,
    ProviderUnavailable,
    TransientProviderError,
)
from app.modules.llm_gateway.providers.anthropic_provider import AnthropicProvider
from app.modules.llm_gateway.providers.openai_provider import OpenAIProvider
from app.modules.llm_gateway.types import CompletionRequest, Message

REQ = CompletionRequest(
    system="Be brief.",
    messages=[Message("user", "hi"), Message("assistant", "hello"), Message("user", "again")],
)
SCHEMA = {"type": "object", "properties": {"intent": {"type": "string"}}, "required": ["intent"]}


# ---- Anthropic -----------------------------------------------------------


class FakeAnthropicMessages:
    def __init__(self, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}
        self.error = error

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text="ok"),
            ],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=3,
                cache_creation_input_tokens=None,
            ),
            stop_reason="end_turn",
        )

    def stream(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        message = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ab")],
            usage=SimpleNamespace(input_tokens=1, output_tokens=2, cache_read_input_tokens=0),
            stop_reason="end_turn",
        )

        class Stream:
            async def __aenter__(self_inner) -> "Stream":
                return self_inner

            async def __aexit__(self_inner, *exc: object) -> None:
                return None

            @property
            def text_stream(self_inner) -> Any:
                async def gen() -> Any:
                    yield "a"
                    yield "b"

                return gen()

            async def get_final_message(self_inner) -> Any:
                return message

        return Stream()


def _anthropic(error: Exception | None = None) -> tuple[AnthropicProvider, FakeAnthropicMessages]:
    messages = FakeAnthropicMessages(error)
    return AnthropicProvider(client=SimpleNamespace(messages=messages)), messages


async def test_anthropic_request_shape() -> None:
    provider, fake = _anthropic()
    target = Target(provider="anthropic", model="claude-haiku-5-5", effort="low")
    response = await provider.complete(target, REQ, 500)
    assert response.text == "ok"  # thinking blocks are ignored
    assert (response.usage.input_tokens, response.usage.cached_input_tokens) == (10, 3)
    kw = fake.kwargs
    assert kw["model"] == "claude-haiku-5-5" and kw["max_tokens"] == 500
    assert kw["system"] == "Be brief."
    assert kw["messages"][1] == {"role": "assistant", "content": "hello"}
    assert kw["output_config"] == {"effort": "low"}
    # Sampling parameters and thinking budgets are rejected by current models: never sent.
    assert "temperature" not in kw and "thinking" not in kw


async def test_anthropic_structured_output_and_cache_marker() -> None:
    provider, fake = _anthropic()
    target = Target(provider="anthropic", model="claude-sonnet-5-5")
    await provider.complete(
        target,
        CompletionRequest(
            messages=REQ.messages, system="Stable prefix", response_schema=SCHEMA, cache_system=True
        ),
        100,
    )
    kw = fake.kwargs
    assert kw["system"] == [
        {"type": "text", "text": "Stable prefix", "cache_control": {"type": "ephemeral"}}
    ]
    assert kw["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}


async def test_anthropic_stream() -> None:
    provider, _ = _anthropic()
    chunks = [c async for c in provider.stream(Target(provider="anthropic", model="m"), REQ, 10)]
    assert [c.text for c in chunks if c.text] == ["a", "b"]
    assert chunks[-1].final is not None and chunks[-1].final.text == "ab"


def _a_status(status: int) -> anthropic.APIStatusError:
    response = httpx2.Response(status, request=httpx2.Request("POST", "https://x.test"))
    return anthropic.APIStatusError("boom", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_a_status(429), TransientProviderError),
        (_a_status(529), TransientProviderError),
        (_a_status(500), TransientProviderError),
        (_a_status(401), ProviderUnavailable),
        (_a_status(400), InvalidRequestError),
        (
            anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x.test")),
            TransientProviderError,
        ),
    ],
)
async def test_anthropic_error_mapping(error: Exception, expected: type[Exception]) -> None:
    provider, _ = _anthropic(error)
    with pytest.raises(expected):
        await provider.complete(Target(provider="anthropic", model="m"), REQ, 10)


async def test_anthropic_has_no_embeddings() -> None:
    provider, _ = _anthropic()
    with pytest.raises(InvalidRequestError):
        await provider.embed(Target(provider="anthropic", model="m"), ["x"])


# ---- OpenAI --------------------------------------------------------------


class FakeCompletions:
    def __init__(self, error: Exception | None = None) -> None:
        self.kwargs: dict[str, Any] = {}
        self.error = error

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        if kwargs.get("stream"):

            async def gen() -> Any:
                yield SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="x"), finish_reason=None)
                    ],
                )
                yield SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="y"), finish_reason="stop")
                    ],
                )
                yield SimpleNamespace(
                    usage=SimpleNamespace(
                        prompt_tokens=7, completion_tokens=2, prompt_tokens_details=None
                    ),
                    choices=[],
                )

            return gen()
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="done"), finish_reason="stop")
            ],
            usage=SimpleNamespace(
                prompt_tokens=20,
                completion_tokens=4,
                prompt_tokens_details=SimpleNamespace(cached_tokens=5),
            ),
        )


class FakeEmbeddings:
    async def create(self, **kwargs: Any) -> Any:
        return SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2]) for _ in kwargs["input"]],
            usage=SimpleNamespace(prompt_tokens=4),
        )


def _openai(error: Exception | None = None) -> tuple[OpenAIProvider, FakeCompletions]:
    completions = FakeCompletions(error)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions), embeddings=FakeEmbeddings()
    )
    return OpenAIProvider(client=client), completions


async def test_openai_request_shape_and_usage() -> None:
    provider, fake = _openai()
    target = Target(provider="openai", model="gpt-x", effort="xhigh")
    response = await provider.complete(
        target,
        CompletionRequest(messages=REQ.messages, system="Be brief.", response_schema=SCHEMA),
        300,
    )
    assert response.text == "done"
    assert (response.usage.input_tokens, response.usage.cached_input_tokens) == (15, 5)
    kw = fake.kwargs
    assert kw["messages"][0] == {"role": "system", "content": "Be brief."}
    assert kw["max_completion_tokens"] == 300
    assert kw["reasoning_effort"] == "high"  # xhigh/max are clamped for this provider
    assert kw["response_format"]["json_schema"]["schema"] == SCHEMA


async def test_openai_stream_collects_text_and_usage() -> None:
    provider, fake = _openai()
    chunks = [c async for c in provider.stream(Target(provider="openai", model="m"), REQ, 10)]
    assert [c.text for c in chunks if c.text] == ["x", "y"]
    final = chunks[-1].final
    assert final is not None and final.text == "xy" and final.usage.input_tokens == 7
    assert fake.kwargs["stream_options"] == {"include_usage": True}


async def test_openai_embeddings() -> None:
    provider, _ = _openai()
    vectors, usage = await provider.embed(Target(provider="openai", model="e"), ["a", "b"])
    assert vectors == [[0.1, 0.2], [0.1, 0.2]] and usage.input_tokens == 4


def _o_status(status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", "https://x.test"))
    return openai.APIStatusError("boom", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (_o_status(429), TransientProviderError),
        (_o_status(503), TransientProviderError),
        (_o_status(401), ProviderUnavailable),
        (_o_status(422), InvalidRequestError),
        (
            openai.APITimeoutError(request=httpx.Request("POST", "https://x.test")),
            TransientProviderError,
        ),
    ],
)
async def test_openai_error_mapping(error: Exception, expected: type[Exception]) -> None:
    provider, _ = _openai(error)
    with pytest.raises(expected):
        await provider.complete(Target(provider="openai", model="m"), REQ, 10)
