from pathlib import Path
from typing import Any

import yaml

from app.modules.evaluation.schema import FixtureSource, PreservationCase, Scenario, SubstancePair


def find_evals_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "evals"
        if (candidate / "scenarios").is_dir():
            return candidate
    raise FileNotFoundError("Could not find the evals directory")


def _load_list(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: expected a list of entries")
    return data


def load_scenarios(root: Path | None = None) -> dict[str, list[Scenario]]:
    """Mentoring scenarios by pack name (the file name), plus the safety suite under 'safety'."""
    root = root or find_evals_dir()
    packs: dict[str, list[Scenario]] = {}
    seen: set[str] = set()
    for path in sorted((root / "scenarios").glob("*.yaml")):
        scenarios = [Scenario.model_validate(item) for item in _load_list(path)]
        for scenario in scenarios:
            if scenario.id in seen:
                raise ValueError(f"Duplicate scenario id {scenario.id}")
            seen.add(scenario.id)
        packs[path.stem] = scenarios
    return packs


def load_substance(root: Path | None = None) -> list[SubstancePair]:
    path = (root or find_evals_dir()) / "substance.yaml"
    return [SubstancePair.model_validate(i) for i in _load_list(path)] if path.exists() else []


def load_preservation(root: Path | None = None) -> list[PreservationCase]:
    path = (root or find_evals_dir()) / "preservation.yaml"
    return [PreservationCase.model_validate(i) for i in _load_list(path)] if path.exists() else []


def load_fixture_sources(root: Path | None = None) -> dict[str, FixtureSource]:
    path = (root or find_evals_dir()) / "fixtures.yaml"
    if not path.exists():
        return {}
    return {s.slug: s for s in (FixtureSource.model_validate(i) for i in _load_list(path))}
