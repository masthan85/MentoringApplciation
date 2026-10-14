"""One mentoring turn: four stages, one streamed model call.

Stage 1  parallel pre-processing: rules, classification, context loading
Stage 2  deterministic routing and prompt assembly
Stage 3  a single streamed generation
Stage 4  post-processing: output checks, persistence, background jobs

The generator never holds a database connection while the model is streaming.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.db import session_scope
from app.core.jobs import enqueue
from app.modules.llm_gateway import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Message,
    StreamEnd,
    TextDelta,
    current_gateway,
)
from app.modules.memory.retrieval import rank_memories
from app.modules.memory.service import list_memories
from app.modules.orchestration import jobs as orchestration_jobs
from app.modules.orchestration import onboarding, service
from app.modules.orchestration.classifier import Preprocess, classify
from app.modules.orchestration.context import PromptBundle, build_mentoring_prompt
from app.modules.orchestration.models import Conversation
from app.modules.orchestration.routing import FixedReply, ModelRoute, combine_risk, decide
from app.modules.orchestration.sse import sse
from app.modules.persona import service as persona_service
from app.modules.persona.assembly import render_persona_section
from app.modules.persona.registry import PackRegistry
from app.modules.persona.selection import ActivePersona
from app.modules.profile.models import Profile
from app.modules.profile.service import get_or_create_profile, missing_fields
from app.modules.safety import Risk, check_output, scan

log = logging.getLogger("app.pipeline")
HISTORY_LOAD = 16
PROVIDER_ERROR = "I couldn't reach the model just now. Nothing was lost; please try sending that again in a moment."


@dataclass
class UserContext:
    profile: dict[str, Any]
    role_family: str | None
    seniority: str | None
    persona_config: Any
    memories: list[tuple[Any, str]]


async def _load_user_context(user_id: UUID, query: str) -> UserContext:
    async with session_scope(user_id) as session:
        from app.modules.identity.models import User

        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        profile = await get_or_create_profile(session, user)
        config = await persona_service.get_config(session, user_id)
        memories = rank_memories(await list_memories(session, user_id), query)
        return UserContext(
            profile={
                "role_family": profile.role_family,
                "job_title": profile.job_title,
                "seniority": profile.seniority,
                "years_experience": profile.years_experience,
                "stack": list(profile.stack or []),
                "goals_summary": profile.goals_summary,
                "current_challenge": profile.current_challenge,
                "english_variant": "American English"
                if profile.english_variant == "en-US"
                else "British English",
            },
            role_family=profile.role_family,
            seniority=profile.seniority,
            persona_config=config,
            memories=memories,
        )


async def run_turn(
    *, user_id: UUID, conversation_id: UUID, text: str, registry: PackRegistry
) -> AsyncIterator[str]:
    started = time.perf_counter()

    # --- Stage 1: persist the user's message, then pre-process in parallel -------------
    async with session_scope(user_id) as session:
        conversation = await service.get_conversation(session, user_id, conversation_id)
        kind = conversation.kind
        user_message = await service.add_message(session, conversation, "user", text)
        user_message_id = user_message.id
        recent = await service.recent_messages(session, conversation_id, HISTORY_LOAD)
        history = [Message("user" if m.role == "user" else "assistant", m.content) for m in recent]
        summary = conversation.rolling_summary
        total_messages = await service.count_messages(session, conversation_id)
        summarised = conversation.summarised_message_count

    rule_hit = scan(text)
    crisis_by_rule = rule_hit is not None and rule_hit.risk is Risk.CRISIS
    context_task = asyncio.create_task(_load_user_context(user_id, text))
    # While onboarding, read the user's latest answer into the profile *before* replying, so the
    # mentor never asks again for something they have just been told.
    extraction_task = (
        asyncio.create_task(onboarding.extract_profile(history))
        if kind == "onboarding" and not crisis_by_rule
        else None
    )
    pre = Preprocess(source="skipped")
    if not crisis_by_rule:
        # Onboarding users have no profile yet, so the default lens stands in for context.
        pre = await classify(
            text,
            recent=[(m.role, m.content) for m in history[:-1]],
            lens_ids=registry.lens_ids,
            current_lens=registry.defaults.default_lens,
        )
    context = await context_task
    if extraction_task is not None:
        await _apply_profile_draft(user_id, await extraction_task)

    # --- Stage 2: routing and prompt assembly -------------------------------------------
    risk = combine_risk(rule_hit.risk if rule_hit else Risk.NORMAL, pre.risk_class)
    persona = persona_service.resolve(
        registry,
        role_family=context.role_family,
        seniority=context.seniority,
        config=context.persona_config,
        suggested_lens=pre.suggested_lens,
        suggestion_confidence=pre.lens_confidence,
    )
    decision = decide(
        risk,
        rule_reason=rule_hit.reason if rule_hit else None,
        intent=pre.intent,
        text=text,
        kind=kind,
    )
    persona_view = {
        "names": [lens.name for lid in persona.lens_ids if (lens := registry.get(lid))],
        "lens_ids": list(persona.lens_ids),
        "source": persona.source,
    }
    yield sse(
        "meta",
        {
            "conversation_id": str(conversation_id),
            "user_message_id": str(user_message_id),
            "persona": persona_view,
            "intent": pre.intent,
            "risk_class": risk.name.lower(),
        },
    )

    base_meta: dict[str, Any] = {
        "persona_snapshot": persona.snapshot(),
        "intent": pre.intent,
        "domain": pre.domain,
        "risk_class": risk.name.lower(),
        "classifier": pre.source,
    }

    if isinstance(decision, FixedReply):
        yield sse("delta", {"text": decision.text})
        assistant_id = await _persist_assistant(
            user_id,
            conversation_id,
            decision.text,
            {**base_meta, "fixed_reply": decision.kind, "reason": decision.reason},
        )
        log.info("fixed reply", extra={"kind": decision.kind, "reason": decision.reason})
        yield sse("done", {"assistant_message_id": str(assistant_id), "fixed_reply": decision.kind})
        return

    assert isinstance(decision, ModelRoute)
    async with session_scope(user_id) as session:
        profile_row = await get_or_create_profile(session, await _user(session, user_id))
        bundle = _assemble(kind, profile_row, context, persona, registry, history, summary, risk)

    # --- Stage 3: one streamed generation ------------------------------------------------
    parts: list[str] = []
    result: CompletionResult | None = None
    finished = False
    try:
        async for event in current_gateway().stream(
            decision.route,
            CompletionRequest(
                system=bundle.system,
                messages=bundle.messages,
                tags={"conversation_id": str(conversation_id), "kind": kind},
            ),
        ):
            if isinstance(event, TextDelta):
                parts.append(event.text)
                yield sse("delta", {"text": event.text})
            elif isinstance(event, StreamEnd):
                result = event.result
        finished = True
    except LLMError:
        log.exception("generation failed")
        yield sse("error", {"message": PROVIDER_ERROR})
        return
    finally:
        # Provider failure, client disconnect (the generator is cancelled or closed) or any
        # other early exit: keep whatever the user already saw, marked as interrupted.
        if not finished and parts:
            await asyncio.shield(
                _persist_partial(user_id, conversation_id, "".join(parts), base_meta)
            )

    final_text = result.text if result else "".join(parts)

    # --- Stage 4: checks, persistence, background work -----------------------------------
    violations = check_output(final_text)
    if violations:
        log.warning(
            "output check flagged reply", extra={"kinds": sorted({v.kind for v in violations})}
        )
    meta = {
        **base_meta,
        "route": decision.route,
        "provider": result.provider if result else None,
        "model": result.model if result else None,
        "usage": (
            {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cached_input_tokens": result.usage.cached_input_tokens,
            }
            if result
            else None
        ),
        "cost_usd": result.cost_usd if result else None,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "stop_reason": result.stop_reason if result else None,
        "safety_flags": [v.kind for v in violations],
        "prompt_versions": bundle.prompt_versions,
        "section_tokens": bundle.section_tokens,
    }
    assistant_id = await _persist_assistant(user_id, conversation_id, final_text, meta)

    done: dict[str, Any] = {"assistant_message_id": str(assistant_id), "route": decision.route}
    if kind == "onboarding":
        done["profile"] = await _profile_card(user_id)

    await enqueue(
        "extract_memories",
        user_id=str(user_id),
        conversation_id=str(conversation_id),
        user_message_id=str(user_message_id),
        assistant_message_id=str(assistant_id),
    )
    if orchestration_jobs.needs_summary(total_messages + 1, summarised):
        await enqueue(
            "summarise_conversation", user_id=str(user_id), conversation_id=str(conversation_id)
        )
    yield sse("done", done)


async def _user(session: Any, user_id: UUID) -> Any:
    from app.modules.identity.models import User

    return (await session.execute(select(User).where(User.id == user_id))).scalar_one()


def _assemble(
    kind: str,
    profile: Profile,
    context: UserContext,
    persona: ActivePersona,
    registry: PackRegistry,
    history: list[Message],
    summary: str | None,
    risk: Risk,
) -> PromptBundle:
    if kind == "onboarding":
        return onboarding.build_onboarding_prompt(profile, history)
    return build_mentoring_prompt(
        persona_section=render_persona_section(persona, context.seniority, registry),
        profile=context.profile,
        memories=[text for _, text in context.memories],
        rolling_summary=summary,
        history=history,
        regulated=risk is Risk.ADJACENT_REGULATED,
    )


async def _persist_assistant(
    user_id: UUID, conversation_id: UUID, text: str, meta: dict[str, Any]
) -> UUID:
    async with session_scope(user_id) as session:
        conversation: Conversation = await service.get_conversation(
            session, user_id, conversation_id
        )
        message = await service.add_message(session, conversation, "assistant", text, meta)
        return message.id


async def _persist_partial(
    user_id: UUID, conversation_id: UUID, text: str, meta: dict[str, Any]
) -> None:
    if not text:
        return
    await _persist_assistant(user_id, conversation_id, text, {**meta, "interrupted": True})


async def _apply_profile_draft(user_id: UUID, draft: onboarding.ProfileDraft | None) -> None:
    if draft is None:
        return
    async with session_scope(user_id) as session:
        profile = await get_or_create_profile(session, await _user(session, user_id))
        changed = onboarding.merge_draft(profile, draft)
        if changed and profile.onboarding_status == "not_started":
            profile.onboarding_status = "in_progress"


async def _profile_card(user_id: UUID) -> dict[str, Any]:
    async with session_scope(user_id) as session:
        profile = await get_or_create_profile(session, await _user(session, user_id))
        return {
            "missing_fields": missing_fields(profile),
            "role_family": profile.role_family,
            "seniority": profile.seniority,
            "job_title": profile.job_title,
            "years_experience": profile.years_experience,
            "stack": list(profile.stack or []),
            "goals_summary": profile.goals_summary,
            "current_challenge": profile.current_challenge,
            "onboarding_status": profile.onboarding_status,
        }
