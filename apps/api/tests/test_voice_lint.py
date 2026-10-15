"""Lint behaviour on good and bad writing. These examples pin the default thresholds."""

import pytest
from app.modules.voice.lint import lint_text, mean_sentence_cv, thresholds_for

QUESTION = "How should I structure incremental loads for the finance mart?"

GOOD = """Start from what the finance team actually needs refreshed, and how late they can tolerate it. That decides almost everything else. For most marts a daily merge keyed on the business key is enough, with a small overlap window so late-arriving rows are picked up.

Keep the raw extract immutable. If a rerun can rebuild any partition from it, a failure at 3am is a retry rather than a clean-up. What's your current source, a database or files?"""

MECHANICAL = """Great question! You're asking about how to structure incremental loads for the finance mart. It is important to note that incremental loads are a robust and seamless approach. Furthermore, incremental loads are powerful because they reduce cost. Moreover, incremental loads are comprehensive and scalable. Additionally, incremental loads help with performance.

In conclusion, incremental loads are important for your finance mart and incremental loads are robust. I hope this helps!"""


def failed(text: str, **kw: object) -> set[str]:
    return {s.name for s in lint_text(text, user_message=QUESTION, **kw).failed}  # type: ignore[arg-type]


def test_natural_writing_passes() -> None:
    report = lint_text(GOOD, user_message=QUESTION)
    assert report.passed and report.score == 1.0


def test_mechanical_writing_fails_on_the_expected_signals() -> None:
    names = failed(MECHANICAL)
    assert {
        "formulaic_opener",
        "formulaic_closer",
        "discourse_markers",
        "empty_adjectives",
        "question_restatement",
    } <= names


def test_spans_point_at_the_offending_sentences() -> None:
    report = lint_text(MECHANICAL, user_message=QUESTION)
    flagged = [MECHANICAL[s.start : s.end] for s in report.spans]
    assert any(t.startswith("Great question") for t in flagged)
    assert any(t.startswith("Furthermore") for t in flagged)
    assert any("I hope this helps" in t for t in flagged)
    assert not any("Keep the raw extract" in t for t in flagged)
    assert all(
        MECHANICAL[s.start : s.end].strip() == MECHANICAL[s.start : s.end] for s in report.spans
    )


@pytest.mark.parametrize(
    "opener",
    [
        "Certainly! ",
        "Absolutely, ",
        "Of course! ",
        "I'd be happy to help. ",
        "That's a great question. ",
        "Let's dive in. ",
    ],
)
def test_generic_openers_are_caught(opener: str) -> None:
    assert "formulaic_opener" in failed(opener + GOOD)


@pytest.mark.parametrize(
    "closer",
    [
        " I hope this helps.",
        " Let me know if you have any other questions.",
        " Feel free to reach out.",
        " In conclusion, it depends.",
    ],
)
def test_generic_closers_are_caught(closer: str) -> None:
    assert "formulaic_closer" in failed(GOOD + closer)


def test_single_natural_transition_is_fine() -> None:
    text = (
        "The merge approach works for most tables. However, it is slow when the key is wide, so "
        "check the cost on your largest table first and measure before you change anything. "
        "I'd also keep the overlap window small, because every extra day is rescanned each run."
    )
    assert "discourse_markers" not in failed(text)


def test_stacked_transitions_fail_in_context() -> None:
    text = (
        "Furthermore, the job should be idempotent so that a retry never doubles the totals in the report. "
        "Moreover, it should be monitored by the team that owns the source data. Additionally, it should be "
        "documented so that anyone on call can support it at night. Consequently, it will be reliable, and "
        "thus the business can trust the numbers it publishes every morning."
    )
    assert "discourse_markers" in failed(text)


def test_technical_uses_of_robust_are_not_padding() -> None:
    text = (
        "Use robust standard errors here because the residual variance differs by group, and report "
        "them next to the point estimates so that readers can see how much the choice matters for "
        "the conclusions. The model is robust to outliers in the target but not in the features."
    )
    assert "empty_adjectives" not in failed(text)


def test_vague_praise_is_flagged() -> None:
    text = (
        "This is a seamless, powerful and innovative platform with a comprehensive set of cutting-edge "
        "features that unlock robust outcomes for every team that adopts it across the whole business, "
        "and it is a transformative way to work that nobody will want to give up once they have tried it."
    )
    assert "empty_adjectives" in failed(text)


def test_uniform_sentence_lengths_are_flagged() -> None:
    text = " ".join(["The system loads the data every night at two."] * 8)
    assert "sentence_variation" in failed(text)


def test_user_baseline_can_relax_variation_but_not_tighten_it() -> None:
    flat = (
        "The load runs at two. The job writes a file. The team checks the counts. The report goes out. "
        * 3
    )
    default = {s.name: s for s in lint_text(flat).signals}["sentence_variation"]
    relaxed = {s.name: s for s in lint_text(flat, baseline_cv=0.2).signals}["sentence_variation"]
    assert relaxed.threshold < default.threshold
    tightened = {s.name: s for s in lint_text(flat, baseline_cv=5.0).signals}["sentence_variation"]
    assert tightened.threshold == default.threshold


def test_channel_expectations_for_structure() -> None:
    two_bullets = "Options:\n- Merge on the key\n- Full reload\nWe prefer the merge.\nIt is cheaper.\nIt is also safer."
    assert "list_ratio" in failed(two_bullets, channel="chat")  # 2 of 6 lines
    assert "list_ratio" not in failed(two_bullets, channel="exec_summary")
    all_bullets = "Plan:\n- Check the counts\n- Rerun the job\n- Tell the owner\n- Close the ticket\n- Update the runbook"
    assert "list_ratio" in failed(all_bullets, channel="exec_summary")
    headed = "# Context\nWe load data nightly.\nIt is slow.\n# Decision\nWe merge.\nIt is faster.\n# Consequences\nWe test more.\nIt costs time."
    assert "heading_ratio" in failed(headed, channel="email")
    assert "heading_ratio" not in failed(headed, channel="adr")


def test_question_restatement() -> None:
    echo = "You're asking how to structure incremental loads for the finance mart. Use a merge keyed on the business key."
    assert "question_restatement" in failed(echo)
    answer = "Use a merge keyed on the business key, with a short overlap window for late rows."
    assert "question_restatement" not in failed(answer)


def test_conclusion_that_repeats_the_body() -> None:
    text = (
        "Use a merge keyed on the business key for the finance mart loads.\n\n"
        "Keep an overlap window so late rows are picked up on the next run.\n\n"
        "To sum up, use a merge keyed on the business key for the finance mart loads and keep an overlap window for late rows."
    )
    assert "redundant_conclusion" in failed(text)


def test_repeated_phrases_and_openings() -> None:
    text = (
        "The team should check the counts after every load of the finance mart. The team should check the counts "
        "before every release of the report. The team should check the counts when a source system changes its "
        "schema. The team should check the counts at month end before the books close."
    )
    names = failed(text)
    assert "repeated_phrases" in names
    assert "repeated_openings" in names


def test_length_is_judged_against_the_channel_and_mode() -> None:
    long_chat = " ".join(
        f"Point {i} is made here with some detail about the load." for i in range(40)
    )
    assert "length" in failed(long_chat, channel="chat")
    assert "length" not in failed(long_chat, channel="chat", mode="detailed")
    assert "length" not in failed(long_chat, channel="adr")


def test_modes_and_channels_override_thresholds() -> None:
    assert (
        thresholds_for("academic", "chat")["discourse_density_max"]
        > thresholds_for("natural_professional", "chat")["discourse_density_max"]
    )
    assert thresholds_for("natural_professional", "adr")["sentence_cv_min"] == 0.20


def test_code_is_ignored_by_the_lint() -> None:
    text = "Run this:\n```sql\nSELECT furthermore, moreover, additionally FROM robust_seamless_table;\n```\nThen check the counts."
    assert lint_text(text).passed


def test_abbreviations_do_not_split_sentences() -> None:
    text = "Use a columnar format, e.g. Parquet, for the large tables, and keep small lookups in plain files so joins stay cheap and simple."
    report = lint_text(text)
    assert report.word_count > 20
    assert mean_sentence_cv(text) is None  # fewer than four sentences


def test_empty_and_short_text_do_not_crash() -> None:
    assert lint_text("").passed
    assert lint_text("Yes.").passed
    assert lint_text("Thanks, that helps.", user_message="ok").passed


def test_summary_is_json_friendly() -> None:
    import json

    json.dumps(lint_text(MECHANICAL, user_message=QUESTION).summary())
