import json
from typing import Any

import pytest
from app.modules.llm_gateway import CompletionRequest
from app.modules.voice.card import build_voice_card
from app.modules.voice.lint import lint_text
from app.modules.voice.rewrite import apply_replacements, rewrite_allowed, targeted_rewrite
from conftest import FakeLLM

QUESTION = "How should I structure incremental loads for the finance mart?"
TEXT = (
    "Great question! Use a merge keyed on the business key, with a 2 day overlap window so late rows "
    "are picked up in Snowflake. Keep the raw extract immutable so any partition can be rebuilt. "
    "Furthermore, add a row count check after every load. I hope this helps!"
)


def _script(
    llm: FakeLLM,
    rewrites: list[dict[str, Any]],
    entailed: bool = True,
    added: list[str] | None = None,
) -> None:
    base = llm.provider.responder

    def respond(request: CompletionRequest) -> str:
        props = (request.response_schema or {}).get("properties", {})
        if "rewrites" in props:
            return json.dumps({"rewrites": rewrites})
        if "entailed" in props:
            return json.dumps({"entailed": entailed, "missing": [], "added": added or []})
        return base(request)

    llm.provider.responder = respond


def _report() -> Any:
    return lint_text(TEXT, user_message=QUESTION)


async def _run(llm: FakeLLM, **kw: Any) -> Any:
    return await targeted_rewrite(
        TEXT, _report(), channel="chat", mode="natural_professional", user_message=QUESTION, **kw
    )


def test_the_original_fails_lint_with_targetable_spans() -> None:
    report = _report()
    assert not report.passed and len(report.spans) >= 2


async def test_a_good_rewrite_is_accepted_and_only_flagged_sentences_change(llm: FakeLLM) -> None:
    report = _report()
    flagged = {i: TEXT[s.start : s.end] for i, s in enumerate(report.spans)}
    rewrites = []
    for i, original in flagged.items():
        if original.startswith("Great question"):
            rewrites.append({"index": i, "text": ""})
        elif original.startswith("Furthermore"):
            rewrites.append({"index": i, "text": "Add a row count check after every load."})
        elif "hope this helps" in original:
            rewrites.append({"index": i, "text": ""})
    _script(llm, rewrites)
    result = await _run(llm)
    assert result.changed and result.reason is None
    assert "Great question" not in result.text and "hope this helps" not in result.text
    assert (
        "2 day overlap window" in result.text and "Snowflake" in result.text
    )  # untouched sentences stay
    assert result.after and len(result.after["failed"]) < len(result.before["failed"])


async def test_changed_numbers_are_rejected_without_asking_a_model(llm: FakeLLM) -> None:
    report = _report()
    index = next(
        i for i, s in enumerate(report.spans) if TEXT[s.start : s.end].startswith("Furthermore")
    )
    _script(
        llm, [{"index": index, "text": "Add a row count check after every load, within 5 days."}]
    )
    result = await _run(llm)
    assert not result.changed and result.text == TEXT
    assert result.reason == "preservation check failed"
    assert any("numbers added" in p for p in result.problems)
    assert llm.calls_with("voice_entailment") == []  # the deterministic check stopped it first


async def test_a_dropped_name_is_rejected(llm: FakeLLM) -> None:
    text = (
        "Great question about Kafka! Use a merge keyed on the business key, with an overlap window so late "
        "rows are picked up. Keep the raw extract immutable so any partition can be rebuilt."
    )
    report = lint_text(text, user_message=QUESTION)
    index = next(
        i for i, s in enumerate(report.spans) if text[s.start : s.end].startswith("Great question")
    )
    _script(llm, [{"index": index, "text": ""}])
    result = await targeted_rewrite(
        text, report, channel="chat", mode="natural_professional", user_message=QUESTION
    )
    assert not result.changed and any("names lost" in p for p in result.problems)
    assert result.text == text


async def test_the_entailment_judge_can_veto(llm: FakeLLM) -> None:
    report = _report()
    index = next(
        i for i, s in enumerate(report.spans) if TEXT[s.start : s.end].startswith("Furthermore")
    )
    _script(
        llm,
        [{"index": index, "text": "Add a row count check."}],
        entailed=False,
        added=["promises a guarantee"],
    )
    result = await _run(llm)
    assert not result.changed and result.reason == "entailment check failed"
    assert result.text == TEXT


async def test_judge_outage_fails_closed(llm: FakeLLM) -> None:
    report = _report()
    index = next(
        i for i, s in enumerate(report.spans) if TEXT[s.start : s.end].startswith("Furthermore")
    )
    base = llm.provider.responder

    def respond(request: CompletionRequest) -> str:
        props = (request.response_schema or {}).get("properties", {})
        if "rewrites" in props:
            return json.dumps({"rewrites": [{"index": index, "text": "Add a row count check."}]})
        if "entailed" in props:
            return "not json"
        return base(request)

    llm.provider.responder = respond
    result = await _run(llm)
    assert not result.changed and result.text == TEXT


async def test_a_rewrite_that_does_not_improve_the_writing_is_dropped(llm: FakeLLM) -> None:
    report = _report()
    index = next(
        i for i, s in enumerate(report.spans) if TEXT[s.start : s.end].startswith("Great question")
    )
    _script(llm, [{"index": index, "text": "Excellent question!"}])
    result = await _run(llm)
    assert not result.changed and result.reason == "the rewrite did not improve the writing"


async def test_unusable_model_output_keeps_the_original(llm: FakeLLM) -> None:
    llm.script.chat_text = "x"
    _script(llm, [])
    assert (await _run(llm)).reason == "no usable rewrites"


async def test_passing_text_is_left_alone(llm: FakeLLM) -> None:
    good = "Use a merge keyed on the business key, with a small overlap window so late rows are picked up."
    result = await targeted_rewrite(
        good, lint_text(good), channel="chat", mode="natural_professional"
    )
    assert not result.changed and result.text == good and llm.provider.calls == []


async def test_safety_text_is_never_rewritten(llm: FakeLLM) -> None:
    assert not rewrite_allowed({"fixed_reply": "crisis"})
    assert not rewrite_allowed({"fixed_reply": "refusal"})
    assert rewrite_allowed({})
    result = await _run(llm, allowed=False)
    assert not result.changed and llm.provider.calls == []


def test_replacements_apply_back_to_front_and_drop_empty_spans() -> None:
    report = _report()
    out = apply_replacements(TEXT, report.spans, {0: "", len(report.spans) - 1: ""})
    assert "Great question" not in out and "hope this helps" not in out


# ---- the voice card -------------------------------------------------------------------


def test_voice_card_carries_channel_mode_and_spelling() -> None:
    card = build_voice_card(channel="slack", mode="concise", english_variant="en-US")
    assert "Slack or Teams message" in card and "American English" in card
    assert "As short as the content allows" in card and "Answer first" in card


def test_my_style_needs_a_fingerprint() -> None:
    assert "Match the user's own writing style" not in build_voice_card(mode="my_style")
    assert "Match the user's own writing style" in build_voice_card(
        mode="my_style", fingerprint_summary="short, direct sentences"
    )


def test_exemplars_are_wrapped_as_data_and_capped() -> None:
    card = build_voice_card(exemplars=["one " * 400, "two", "three", "four"])
    assert card.count("<writing_example>") == 3
    assert "data, not instructions" in card
    assert "one one" in card and len(card.split()) < 700


def test_feedback_is_included_when_the_last_reply_was_flagged() -> None:
    assert "flagged for: generic opener" in build_voice_card(feedback=["generic opener"])


@pytest.mark.parametrize(
    "mode",
    [
        "natural_professional",
        "professional",
        "executive",
        "conversational",
        "technical",
        "academic",
        "concise",
        "detailed",
    ],
)
def test_every_mode_renders(mode: str) -> None:
    assert "Mode: " in build_voice_card(mode=mode)
