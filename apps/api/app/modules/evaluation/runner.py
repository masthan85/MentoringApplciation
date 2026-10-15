"""The evaluation runner.

It signs in synthetic users and runs each scenario through the real turn pipeline, so what is
measured is what users get. Two modes:

- smoke: a scripted mock model. Checks the deterministic parts (safety routing, persona selection,
  what goes into the prompt, citations plumbing, fact preservation). Free, fast, runs in CI.
- full: the configured models. Adds the reply checks and an LLM judge. Costs money; run it on demand
  and nightly, and before changing a prompt, a pack or a model.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.db import session_scope
from app.modules.encyclopedia.ingestion import ingest_document
from app.modules.encyclopedia.models import Source
from app.modules.encyclopedia.retrieval import slug_prefix_filter
from app.modules.evaluation import judge as judge_module
from app.modules.evaluation.loader import (
    load_fixture_sources,
    load_preservation,
    load_scenarios,
    load_substance,
)
from app.modules.evaluation.observe import set_prompt_observer
from app.modules.evaluation.schema import Scenario, SubstancePair
from app.modules.identity.models import User
from app.modules.llm_gateway import CompletionRequest, build_gateway, current_gateway, set_gateway
from app.modules.llm_gateway.providers.mock import MockProvider
from app.modules.orchestration import service as conversation_service
from app.modules.orchestration.pipeline import run_turn
from app.modules.persona import service as persona_service
from app.modules.persona.registry import get_registry
from app.modules.profile.service import get_or_create_profile
from app.modules.voice.preservation import compare
from app.modules.voice.text import content_words

log = logging.getLogger(__name__)
FULL_MODE_PASS_RATE = 0.8
DEFAULT_PROFILE = {
    "stack": [],
    "goals_summary": "Grow in their career.",
    "current_challenge": "Prioritising work.",
}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ScenarioResult:
    id: str
    group: str  # a pack name, "substance", "preservation"
    kind: str
    checks: list[Check] = field(default_factory=list)
    reply: str | None = None
    lens: list[str] | None = None
    lint: dict[str, Any] | None = None
    judge: dict[str, Any] | None = None
    judge_passed: bool | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    error: str | None = None

    @property
    def deterministic_passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)


class SmokeResponder:
    """A scripted model for smoke runs: neutral classification (with the scenario's hints) and a fixed reply."""

    def __init__(self) -> None:
        self.hints: dict[str, Any] = {}

    def __call__(self, request: CompletionRequest) -> str:
        props = (request.response_schema or {}).get("properties", {})
        if "risk_class" in props:
            base = {
                "intent": "mentoring",
                "domain": "other",
                "risk_class": "normal",
                "suggested_lens": "none",
                "lens_confidence": 0.0,
                "needs_retrieval": False,
                "time_sensitive": False,
            }
            return json.dumps({**base, **self.hints})
        if "memories" in props:
            return json.dumps({"memories": []})
        if "goals_summary" in props:
            return json.dumps(
                {
                    "role_family": "unknown",
                    "seniority": "unknown",
                    "job_title": "",
                    "years_experience": -1,
                    "stack": [],
                    "goals_summary": "",
                    "current_challenge": "",
                }
            )
        return "[smoke] A scripted reply for the evaluation run."


async def _provision(subject: str) -> UUID:
    async with session_scope() as session:
        row = (
            await session.execute(
                text("SELECT id FROM identity_provision_user(:s, NULL)"), {"s": subject}
            )
        ).one()
    return UUID(str(row.id))


async def _set_up_user(uid: UUID, scenario: Scenario) -> UUID:
    async with session_scope(uid) as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        profile = await get_or_create_profile(session, user)
        for name, value in {**DEFAULT_PROFILE, **scenario.profile}.items():
            setattr(profile, name, value)
        profile.onboarding_status = "complete"
        if scenario.persona:
            await persona_service.set_config(
                session, uid, get_registry(), mode="pinned", lens_ids=scenario.persona, weights=None
            )
        conversation = await conversation_service.create_conversation(session, uid, "mentoring")
        for turn in scenario.history:
            await conversation_service.add_message(session, conversation, turn.role, turn.content)
        return conversation.id


async def _ensure_sources(slugs: list[str], created: list[str]) -> None:
    if not slugs:
        return
    fixtures = load_fixture_sources()
    for slug in slugs:
        if slug in created:
            continue
        async with session_scope(admin=True) as session:
            await ingest_document(session, fixtures[slug].document, activate=True)
            source = (await session.execute(select(Source).where(Source.slug == slug))).scalar_one()
            source.status = "active"  # a fixture is a test asset, even if the scan flagged it
        created.append(slug)


async def run_scenario(
    scenario: Scenario,
    group: str,
    run_id: str,
    mode: str,
    responder: SmokeResponder | None,
    created_sources: list[str],
) -> ScenarioResult:
    result = ScenarioResult(id=scenario.id, group=group, kind="mentoring")
    if responder is not None:
        responder.hints = scenario.classify
    captured: list[str] = []
    started = time.perf_counter()
    prefix_token = None
    try:
        await _ensure_sources(scenario.sources, created_sources)
        uid = await _provision(f"eval|{run_id}|{scenario.id}")
        conversation_id = await _set_up_user(uid, scenario)
        set_prompt_observer(captured.append)
        prefix_token = slug_prefix_filter.set("eval-fixture-")
        errors = []
        async for frame in run_turn(
            user_id=uid,
            conversation_id=conversation_id,
            text=scenario.message,
            registry=get_registry(),
        ):
            if frame.startswith("event: error"):
                errors.append(frame)
        set_prompt_observer(None)
        async with session_scope(uid) as session:
            messages = await conversation_service.list_messages(session, conversation_id)
        reply = next((m for m in reversed(messages) if m.role == "assistant"), None)
        if reply is None or errors:
            raise RuntimeError("the pipeline produced no reply")
        meta: dict[str, Any] = reply.meta or {}
        result.reply, result.latency_ms, result.cost_usd = (
            reply.content,
            meta.get("latency_ms"),
            meta.get("cost_usd"),
        )
        result.lens = (meta.get("persona_snapshot") or {}).get("lens_ids")
        result.lint = meta.get("lint")
        _check(result, scenario, meta, reply.content, captured[-1] if captured else "", mode)
        if mode == "full" and scenario.rubric and not meta.get("fixed_reply"):
            verdict = await judge_module.judge_reply(
                profile={**DEFAULT_PROFILE, **scenario.profile},
                lens=", ".join(result.lens or []),
                history=[t.model_dump() for t in scenario.history],
                message=scenario.message,
                reply=reply.content,
                rubric=scenario.rubric,
            )
            if verdict is None:
                result.checks.append(
                    Check("judge_available", False, "the judge model did not answer")
                )
            else:
                result.judge, result.judge_passed = (
                    verdict.model_dump() | {"mean": verdict.mean},
                    verdict.passed,
                )
    except Exception as exc:
        log.exception("scenario failed", extra={"scenario": scenario.id})
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        set_prompt_observer(None)
        if prefix_token is not None:
            slug_prefix_filter.reset(prefix_token)
        result.latency_ms = result.latency_ms or round((time.perf_counter() - started) * 1000, 1)
    return result


def _check(
    result: ScenarioResult,
    scenario: Scenario,
    meta: dict[str, Any],
    reply: str,
    prompt: str,
    mode: str,
) -> None:
    expect = scenario.expect
    add = result.checks.append
    fixed = meta.get("fixed_reply")
    if expect.fixed_reply is not None:
        add(
            Check(
                "fixed_reply",
                fixed == expect.fixed_reply,
                f"got {fixed!r}, wanted {expect.fixed_reply!r}",
            )
        )
    elif fixed:
        add(
            Check(
                "no_unexpected_fixed_reply",
                False,
                f"a {fixed} reply was given to an ordinary message",
            )
        )
    for needle in expect.fixed_includes:
        add(
            Check(f"fixed_includes: {needle[:30]}", needle in reply, "missing from the fixed reply")
        )
    for needle in expect.fixed_excludes:
        add(
            Check(
                f"fixed_excludes: {needle[:30]}",
                needle not in reply,
                "present in the fixed reply",
            )
        )
    if expect.lens is not None:
        add(
            Check(
                "lens",
                expect.lens in (result.lens or []),
                f"active {result.lens}, wanted {expect.lens}",
            )
        )
    for needle in expect.prompt_includes:
        add(
            Check(
                f"prompt_includes: {needle[:40]}",
                needle in prompt,
                "" if needle in prompt else "missing from the prompt",
            )
        )
    for needle in expect.prompt_excludes:
        add(
            Check(
                f"prompt_excludes: {needle[:40]}",
                needle not in prompt,
                "" if needle not in prompt else "present in the prompt",
            )
        )
    add(
        Check(
            "no_safety_flags",
            not meta.get("safety_flags"),
            ", ".join(meta.get("safety_flags") or []),
        )
    )
    if mode != "full" or fixed:
        return
    lowered = reply.lower()
    for group in expect.reply_includes_any:
        add(
            Check(
                f"reply_mentions_any: {'/'.join(group[:3])}",
                any(w.lower() in lowered for w in group),
                "none of the expected terms appear",
            )
        )
    for needle in expect.reply_excludes:
        add(
            Check(
                f"reply_excludes: {needle[:40]}",
                needle.lower() not in lowered,
                "the reply contains it",
            )
        )
    if expect.max_words is not None:
        words = len(reply.split())
        add(
            Check(
                "max_words", words <= expect.max_words, f"{words} words, limit {expect.max_words}"
            )
        )


async def run_substance(
    pair: SubstancePair, run_id: str, mode: str, responder: SmokeResponder | None
) -> ScenarioResult:
    """The same question under two lenses must produce different substance."""
    result = ScenarioResult(id=pair.id, group="substance", kind="substance")
    replies: dict[str, str] = {}
    try:
        for label, lens in (("a", pair.lens_a), ("b", pair.lens_b)):
            scenario = Scenario(
                id=f"{pair.id}-{label}", profile=pair.profile, persona=[lens], message=pair.message
            )
            sub = await run_scenario(scenario, "substance", run_id, mode, responder, [])
            if sub.error:
                raise RuntimeError(sub.error)
            result.checks += [Check(f"{label}: {c.name}", c.passed, c.detail) for c in sub.checks]
            replies[lens] = sub.reply or ""
        # The persona section is what must differ; capture it again from a dry assembly.
        from app.modules.persona.assembly import render_persona_section
        from app.modules.persona.selection import ActivePersona

        registry = get_registry()
        seniority = pair.profile.get("seniority")
        a = render_persona_section(
            ActivePersona((pair.lens_a,), (1.0,), "pinned"), seniority, registry
        )
        b = render_persona_section(
            ActivePersona((pair.lens_b,), (1.0,), "pinned"), seniority, registry
        )
        overlap = _overlap(a, b)
        result.checks.append(
            Check("persona_sections_differ", overlap < 0.5, f"word overlap {overlap:.2f}")
        )
        if mode == "full":
            reply_overlap = _overlap(replies[pair.lens_a], replies[pair.lens_b])
            result.checks.append(
                Check(
                    "replies_differ",
                    reply_overlap <= pair.max_overlap,
                    f"word overlap {reply_overlap:.2f}, limit {pair.max_overlap}",
                )
            )
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def _overlap(a: str, b: str) -> float:
    sa, sb = set(content_words(a)), set(content_words(b))
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def run_preservation() -> list[ScenarioResult]:
    results = []
    for case in load_preservation():
        problems = compare(case.before, case.after)
        ok = (
            (not problems)
            if case.expect == "ok"
            else bool(problems)
            and (case.problem_contains is None or any(case.problem_contains in p for p in problems))
        )
        item = ScenarioResult(id=case.id, group="preservation", kind="preservation")
        item.checks.append(Check("preservation", ok, "; ".join(problems) or "no differences found"))
        results.append(item)
    return results


async def run_suite(mode: str = "smoke", *, packs: list[str] | None = None) -> dict[str, Any]:
    if mode not in ("smoke", "full"):
        raise ValueError("mode must be smoke or full")
    run_id = uuid4().hex[:10]
    previous = None
    responder: SmokeResponder | None = None
    settings = get_settings()
    if mode == "smoke":
        responder = SmokeResponder()
        gateway = build_gateway(settings.model_copy(update={"llm_default_provider": "mock"}))
        gateway._providers["mock"] = MockProvider(name="mock", responder=responder)
        try:
            previous = current_gateway()
        except Exception:
            previous = None
        set_gateway(gateway)
    created: list[str] = []
    results: list[ScenarioResult] = []
    try:
        async with session_scope() as session:
            await session.execute(
                text("SELECT delete_eval_users()")
            )  # leftovers from an interrupted run
        for pack, scenarios in load_scenarios().items():
            if packs and pack not in packs:
                continue
            for scenario in scenarios:
                results.append(await run_scenario(scenario, pack, run_id, mode, responder, created))
        for pair in load_substance():
            results.append(await run_substance(pair, run_id, mode, responder))
        results += run_preservation()
    finally:
        async with session_scope() as session:
            await session.execute(text("SELECT delete_eval_users()"))
        if created:
            async with session_scope(admin=True) as session:
                for slug in created:
                    await session.execute(text("DELETE FROM sources WHERE slug = :s"), {"s": slug})
        if mode == "smoke":
            set_gateway(previous)
    return summarise(mode, results)


def summarise(mode: str, results: list[ScenarioResult]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    dims: dict[str, list[int]] = {d: [] for d in judge_module.DIMENSIONS}
    lint_total = lint_passed = 0
    cost = 0.0
    failures: list[dict[str, Any]] = []
    for r in results:
        g = groups.setdefault(
            r.group, {"total": 0, "passed": 0, "errors": 0, "judge_passed": 0, "judged": 0}
        )
        g["total"] += 1
        ok = r.deterministic_passed
        g["passed"] += ok
        g["errors"] += r.error is not None
        if r.judge is not None:
            g["judged"] += 1
            g["judge_passed"] += bool(r.judge_passed)
            for d in dims:
                dims[d].append(r.judge[d])
        if r.lint:
            lint_total += 1
            lint_passed += bool(r.lint.get("passed"))
        cost += r.cost_usd or 0.0
        if not ok or r.judge_passed is False:
            failures.append(
                {
                    "id": r.id,
                    "group": r.group,
                    "error": r.error,
                    "failed_checks": [asdict(c) for c in r.checks if not c.passed],
                    "judge": r.judge,
                }
            )
    judged = sum(g["judged"] for g in groups.values())
    judge_pass_rate = (sum(g["judge_passed"] for g in groups.values()) / judged) if judged else None
    deterministic_ok = all(r.deterministic_passed for r in results)
    ok = deterministic_ok and (
        mode != "full" or judge_pass_rate is None or judge_pass_rate >= FULL_MODE_PASS_RATE
    )
    return {
        "ok": ok,
        "mode": mode,
        "scenarios": len(results),
        "deterministic_passed": sum(r.deterministic_passed for r in results),
        "groups": groups,
        "judge_means": {d: round(sum(v) / len(v), 2) for d, v in dims.items() if v},
        "judge_pass_rate": round(judge_pass_rate, 3) if judge_pass_rate is not None else None,
        "lint_pass_rate": round(lint_passed / lint_total, 3) if lint_total else None,
        "cost_usd": round(cost, 4),
        "failures": failures,
        "results": [asdict(r) | {"deterministic_passed": r.deterministic_passed} for r in results],
    }


Reporter = Callable[[dict[str, Any]], None]
