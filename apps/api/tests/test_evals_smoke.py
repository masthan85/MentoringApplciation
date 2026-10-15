"""The shipped scenario files must pass the deterministic smoke run (what CI runs)."""

from app.modules.evaluation.loader import load_scenarios
from app.modules.evaluation.runner import run_suite
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_scenario_files_are_valid_and_cover_every_pack() -> None:
    groups = load_scenarios()
    assert set(groups) >= {"data-engineering", "ai-engineering", "leadership-career", "safety"}
    ids = [s.id for scenarios in groups.values() for s in scenarios]
    assert len(ids) == len(set(ids))


async def test_smoke_suite_passes(db: AsyncEngine) -> None:
    summary = await run_suite("smoke")
    assert summary["ok"], summary["failures"]
