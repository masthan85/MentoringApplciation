"""The preservation suite: what a rewrite must never change."""

import pytest
from app.modules.voice.preservation import compare, extract_facts

ORIGINAL = (
    "We moved the nightly load to Snowflake on 12 March 2026 and it now runs v2.3.1 of the dbt package. "
    "Costs fell from £4,200 to £3,150 a month (25%). Details: https://example.com/runbook, "
    "and run `dbt build --select tag:finance` after the Airflow DAG finishes."
)


def test_identical_text_has_no_problems() -> None:
    assert compare(ORIGINAL, ORIGINAL) == []


def test_rephrasing_that_keeps_every_fact_is_fine() -> None:
    rewritten = (
        "Since the Airflow DAG finishes first, run `dbt build --select tag:finance` next. The nightly load "
        "moved to Snowflake on 12 March 2026 and now runs v2.3.1 of the dbt package. Costs fell from "
        "£4,200 to £3,150 a month (25%). Runbook: https://example.com/runbook"
    )
    assert compare(ORIGINAL, rewritten) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda t: t.replace("£3,150", "£3,000"), "numbers"),
        (lambda t: t.replace("25%", "30%"), "numbers"),
        (lambda t: t.replace("v2.3.1", "v2.3.2"), "versions"),
        (lambda t: t.replace("12 March 2026", "13 March 2026"), "dates"),
        (lambda t: t.replace("https://example.com/runbook", "https://example.com/other"), "urls"),
        (lambda t: t.replace("tag:finance", "tag:sales"), "code"),
        (lambda t: t.replace("Snowflake", "BigQuery"), "names"),
        (lambda t: t.replace("Airflow", "Prefect"), "names"),
    ],
)
def test_any_changed_fact_is_caught(change, expected: str) -> None:  # type: ignore[no-untyped-def]
    problems = compare(ORIGINAL, change(ORIGINAL))
    assert any(expected in p for p in problems), problems


def test_dropping_a_number_is_caught() -> None:
    assert any("numbers lost" in p for p in compare(ORIGINAL, ORIGINAL.replace(" (25%)", "")))


def test_adding_a_new_number_or_name_is_caught() -> None:
    assert any(
        "numbers added" in p for p in compare(ORIGINAL, ORIGINAL + " That is 3 times cheaper.")
    )
    assert any(
        "names added" in p for p in compare(ORIGINAL, ORIGINAL + " The load is watched by Datadog.")
    )


def test_a_new_name_at_the_start_of_a_sentence_is_left_to_the_judge() -> None:
    """Sentence-initial words cannot be told from ordinary capitalised words, so the claim-level
    check (not this deterministic one) is what catches an invented name there."""
    assert compare(ORIGINAL, ORIGINAL + " Datadog watches it.") == []


def test_code_blocks_must_be_identical() -> None:
    before = "Run:\n```sql\nSELECT id FROM orders WHERE status = 'open';\n```\nThen check."
    after = "Run:\n```sql\nSELECT id FROM orders WHERE status = 'closed';\n```\nThen check."
    assert any("code" in p for p in compare(before, after))


def test_number_formats_are_normalised() -> None:
    assert compare("Spend was 1,200 in total.", "In total, spend was 1200.") == []


def test_sentence_start_capitalisation_is_not_a_name() -> None:
    assert (
        compare("Honestly the plan is sound. Then we ship.", "The plan is sound, and then we ship.")
        == []
    )


def test_extraction_finds_the_expected_kinds() -> None:
    facts = extract_facts(ORIGINAL)
    assert "https://example.com/runbook" in facts.urls
    assert "12 march 2026" in facts.dates
    assert "v2.3.1" in facts.versions
    assert {"4200", "3150"} <= {n.lstrip("£") for n in facts.numbers}
    assert "dbt build --select tag:finance" in facts.code
    assert {"Snowflake", "Airflow"} <= facts.entities_inner
