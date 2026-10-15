from pathlib import Path

import pytest
import yaml
from app.modules.persona.assembly import render_persona_section
from app.modules.persona.registry import PackError, get_registry, load_registry
from app.modules.persona.selection import ActivePersona, select_persona
from app.modules.profile.taxonomy import RoleFamily, Seniority

PACKS = Path(__file__).resolve().parents[3] / "packs"


def test_the_three_mvp_packs_load() -> None:
    registry = get_registry()
    assert set(registry.packs) == {"data-engineering", "ai-engineering", "leadership-career"}
    assert len(registry.lenses) == 7


def test_every_role_and_seniority_resolves_to_a_real_lens() -> None:
    registry = get_registry()
    for role in RoleFamily:
        for level in [*Seniority, None]:
            lens_id = registry.default_for(role.value, level.value if level else None)
            assert registry.get(lens_id) is not None, (role, level)
    assert registry.get(registry.default_for(None, None)) is not None


def test_data_engineer_default_changes_with_seniority() -> None:
    registry = get_registry()
    assert registry.default_for("data_engineer", "mid") == "senior-data-engineer"
    assert registry.default_for("data_engineer", "lead") == "data-architect"


def test_lenses_are_perspectives_not_biographies() -> None:
    for lens in get_registry().lenses.values():
        text = lens.perspective.lower()
        assert text.startswith("the perspective of"), lens.id
        assert " i " not in f" {text} ", lens.id


def test_persona_changes_the_substance_not_just_the_tone() -> None:
    """Same user, different lens: different priorities, questions and failure modes."""
    registry = get_registry()
    engineer = render_persona_section(
        ActivePersona(("senior-data-engineer",), (1.0,), "pinned"), "senior", registry
    )
    architect = render_persona_section(
        ActivePersona(("data-architect",), (1.0,), "pinned"), "senior", registry
    )
    assert (
        "Idempotency and recoverability" in engineer
        and "Idempotency and recoverability" not in architect
    )
    assert "Total cost of ownership" in architect and "Total cost of ownership" not in engineer
    assert engineer != architect
    shared_lines = set(engineer.splitlines()) & set(architect.splitlines())
    substantive = {line for line in shared_lines if line.startswith("- ")}
    assert len(substantive) <= 1


def test_depth_follows_seniority() -> None:
    registry = get_registry()
    persona = ActivePersona(("ml-engineer",), (1.0,), "default")
    junior = render_persona_section(persona, "junior", registry)
    lead = render_persona_section(persona, "lead", registry)
    assert "Build sound habits" in junior and "Build sound habits" not in lead
    assert "Explain these terms briefly" in junior and "Explain these terms briefly" not in lead


def test_two_lenses_blend_by_weight() -> None:
    registry = get_registry()
    heavy_architect = render_persona_section(
        ActivePersona(("data-architect", "ai-risk-and-security"), (0.8, 0.2), "pinned"),
        "senior",
        registry,
    )
    heavy_security = render_persona_section(
        ActivePersona(("data-architect", "ai-risk-and-security"), (0.2, 0.8), "pinned"),
        "senior",
        registry,
    )
    priorities = lambda s: s.split("most important first:")[1].split("Questions")[0]  # noqa: E731
    assert priorities(heavy_architect).splitlines()[1] != priorities(heavy_security).splitlines()[1]
    # Each lens always shows up, and the heavier one contributes more of its own priorities.
    assert "Understanding what data and permissions" in heavy_architect
    assert "Fitness for the business decisions" in heavy_security
    assert "Threat modelling" in heavy_security and "Threat modelling" not in heavy_architect


def _select(**kw: object) -> ActivePersona:
    base = {
        "registry": get_registry(),
        "role_family": "data_engineer",
        "seniority": "senior",
        "pinned_lens_ids": None,
        "pinned_weights": None,
        "suggested_lens": None,
        "suggestion_confidence": 0.0,
        "threshold": 0.7,
    }
    return select_persona(**{**base, **kw})  # type: ignore[arg-type]


def test_selection_authority_order() -> None:
    assert _select().source == "default"
    confident = _select(suggested_lens="ai-risk-and-security", suggestion_confidence=0.9)
    assert (confident.lens_ids, confident.source) == (("ai-risk-and-security",), "classifier")
    assert (
        _select(suggested_lens="ai-risk-and-security", suggestion_confidence=0.5).source
        == "default"
    )
    pinned = _select(
        pinned_lens_ids=["data-architect"],
        suggested_lens="ai-risk-and-security",
        suggestion_confidence=1.0,
    )
    assert (pinned.lens_ids, pinned.source) == (("data-architect",), "pinned")  # user choice wins


def test_suggesting_the_current_default_is_not_a_switch() -> None:
    assert (
        _select(suggested_lens="senior-data-engineer", suggestion_confidence=0.99).source
        == "default"
    )


def test_unknown_suggestions_and_pins_are_ignored() -> None:
    assert _select(suggested_lens="made-up", suggestion_confidence=0.99).source == "default"
    assert _select(pinned_lens_ids=["made-up"]).source == "default"


def test_at_most_two_lenses_are_pinned() -> None:
    result = _select(pinned_lens_ids=["data-architect", "ml-engineer", "genai-engineer"])
    assert len(result.lens_ids) == 2
    assert sum(result.weights) == pytest.approx(1.0)


def _copy_packs(tmp_path: Path) -> Path:
    for f in PACKS.glob("*.yaml"):
        (tmp_path / f.name).write_text(f.read_text())
    return tmp_path


def test_invalid_pack_is_rejected_at_load(tmp_path: Path) -> None:
    directory = _copy_packs(tmp_path)
    data = yaml.safe_load((directory / "ai-engineering.yaml").read_text())
    del data["lenses"][0]["depth_by_seniority"]["executive"]
    (directory / "ai-engineering.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(PackError, match="depth_by_seniority"):
        load_registry(directory)


def test_first_person_perspective_is_rejected(tmp_path: Path) -> None:
    directory = _copy_packs(tmp_path)
    data = yaml.safe_load((directory / "ai-engineering.yaml").read_text())
    data["lenses"][0]["perspective"] = "I have spent twenty years building models."
    (directory / "ai-engineering.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(PackError, match="third person"):
        load_registry(directory)


def test_defaults_must_reference_real_lenses(tmp_path: Path) -> None:
    directory = _copy_packs(tmp_path)
    data = yaml.safe_load((directory / "defaults.yaml").read_text())
    data["default_lens"] = "nope"
    (directory / "defaults.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(PackError, match="unknown lenses"):
        load_registry(directory)


def test_duplicate_lens_ids_are_rejected(tmp_path: Path) -> None:
    directory = _copy_packs(tmp_path)
    (directory / "copy.yaml").write_text(
        (directory / "ai-engineering.yaml").read_text().replace("id: ai-engineering", "id: copy")
    )
    with pytest.raises(PackError, match="Duplicate lens id"):
        load_registry(directory)
