"""Run the evaluation suite from the command line.

    uv run python scripts/run_evals.py --mode smoke            (CI: no keys needed)
    uv run python scripts/run_evals.py --mode full --label "before changing the data pack"

Exits with status 1 if the run did not pass. Full mode needs real API keys and costs money.
"""

import argparse
import asyncio
import json
import sys

import app.modules.encyclopedia.jobs
import app.modules.memory.jobs
import app.modules.orchestration.jobs  # noqa: F401
from app.core.db import dispose_engine, session_scope
from app.modules.evaluation import service


async def main(mode: str, label: str, packs: list[str] | None, store: bool, as_json: bool) -> int:
    from app.modules.evaluation.runner import run_suite

    summary = await run_suite(mode, packs=packs)
    if store:
        async with session_scope(admin=True) as session:
            run = await service.create_run(session, label, mode)
            run.results = summary.pop("results")
            run.summary = summary
            run.status = "finished"
            from datetime import UTC, datetime

            run.finished_at = datetime.now(UTC)
    results = summary.pop("results", [])
    if as_json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"{'PASS' if summary['ok'] else 'FAIL'}  {mode} run: {summary['deterministic_passed']}/{summary['scenarios']} deterministic checks passed"
        )
        for name, g in summary["groups"].items():
            judged = f", judge {g['judge_passed']}/{g['judged']}" if g["judged"] else ""
            print(f"  {name:22} {g['passed']}/{g['total']}{judged}")
        if summary.get("judge_means"):
            print(
                "  judge means:", summary["judge_means"], "pass rate:", summary["judge_pass_rate"]
            )
        for failure in summary["failures"]:
            print(
                f"  FAILED {failure['id']}: {failure['error'] or [c['name'] + ' - ' + c['detail'] for c in failure['failed_checks']]}"
            )
    del results
    await dispose_engine()
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--label", default="command line")
    parser.add_argument("--pack", action="append", dest="packs")
    parser.add_argument(
        "--store", action="store_true", help="save the run so it shows on the admin page"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.mode, args.label, args.packs, args.store, args.json)))
