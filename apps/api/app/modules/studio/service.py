"""Studio: drafts through the full Natural Voice pipeline."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFound
from app.modules.audit import service as audit
from app.modules.fingerprint import service as fingerprint
from app.modules.identity.models import User
from app.modules.identity.service import consent_state
from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.orchestration.context import SAFETY, format_profile
from app.modules.profile.service import get_or_create_profile
from app.modules.safety import Risk, crisis_message, refusal_message, scan
from app.modules.studio.models import Draft
from app.modules.studio.schemas import DraftOut, DraftRequest
from app.modules.voice.card import build_voice_card
from app.modules.voice.lint import lint_text, load_config
from app.modules.voice.preservation import extract_facts
from app.modules.voice.rewrite import rewrite_allowed, targeted_rewrite
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
DRAFT_PROMPT = ("studio_draft", 1)
MAX_TOKENS = {
    "slack": 400,
    "email": 700,
    "exec_summary": 700,
    "adr": 1800,
    "linkedin": 800,
    "interview_spoken": 700,
}


def unsupported_facts(draft: str, supplied: str) -> list[str]:
    """Numbers, dates, versions and links in the draft that the user never gave. Possible inventions."""
    have, got = extract_facts(supplied), extract_facts(draft)
    warnings: list[str] = []
    for label in ("numbers", "dates", "versions", "urls"):
        extra = getattr(got, label) - getattr(have, label)
        if extra:
            warnings.append(
                f"The draft mentions {label} you did not provide: {', '.join(sorted(extra)[:5])}. Check or remove them."
            )
    return warnings


async def create_draft(session: AsyncSession, user: User, request: DraftRequest) -> DraftOut:
    notes = f"{request.purpose}\n{request.key_points}"
    hit = scan(notes)
    if hit and hit.risk is Risk.CRISIS:
        country = (await get_or_create_profile(session, user)).country
        return DraftOut(refused="crisis", message=crisis_message(country))
    if hit and hit.risk is Risk.PROHIBITED:
        return DraftOut(refused="prohibited", message=refusal_message(hit.reason))

    profile = await get_or_create_profile(session, user)
    mode = (
        request.mode
        if request.mode and request.mode in load_config()["modes"]
        else profile.writing_mode
    )
    context = await fingerprint.context_for(session, user.id, request.channel)
    card = build_voice_card(
        channel=request.channel,
        mode=mode,
        english_variant=profile.english_variant,
        fingerprint_summary=context.summary,
        exemplars=list(context.exemplars),
    )
    profile_text = format_profile(
        {
            "role_family": profile.role_family,
            "job_title": profile.job_title,
            "seniority": profile.seniority,
            "stack": list(profile.stack or []),
        }
    )
    system = "\n\n".join(
        [
            prompts.load(*SAFETY),
            prompts.load(*DRAFT_PROMPT),
            card,
            f"<user_profile>\n{profile_text}\n</user_profile>",
        ]
    )
    brief = (
        f"<channel>{request.channel}</channel>\n<recipient>{request.recipient}</recipient>\n"
        f"<purpose>{request.purpose}</purpose>\n<key_points>\n{request.key_points}\n</key_points>"
    )
    try:
        generated = await current_gateway().complete(
            "chat_large",
            CompletionRequest(
                system=system,
                messages=[Message("user", brief)],
                max_tokens=MAX_TOKENS[request.channel],
                tags={"purpose": "studio_draft", "channel": request.channel},
            ),
        )
    except LLMError as exc:
        raise AppError(
            "The drafting model is unavailable right now. Please try again shortly."
        ) from exc

    text = generated.text.strip()
    # No user_message here: a draft is expected to echo its brief, which is not "restating a question".
    report = lint_text(text, channel=request.channel, mode=mode, baseline_cv=context.baseline_cv)
    adjusted, note, after = False, None, None
    if not report.passed:
        outcome = await targeted_rewrite(
            text,
            report,
            channel=request.channel,
            mode=mode,
            baseline_cv=context.baseline_cv,
            style_note=context.summary or "",
            allowed=rewrite_allowed({}),
        )
        if outcome.changed:
            text, adjusted, after = outcome.text, True, outcome.after
            note = "A few phrases were tidied to read more naturally. The facts are unchanged."
        else:
            note = f"Left as written ({outcome.reason})."

    similarity = await fingerprint.similarity_to(session, user.id, request.channel, text)
    warnings = unsupported_facts(text, f"{notes}\n{profile_text}")
    draft = Draft(
        user_id=user.id,
        channel=request.channel,
        recipient=request.recipient,
        purpose=request.purpose,
        key_points=request.key_points,
        text=text,
        lint=report.summary(),
        similarity=similarity,
        meta={
            "mode": mode,
            "model": generated.model,
            "provider": generated.provider,
            "cost_usd": generated.cost_usd,
            "adjusted": adjusted,
            "after": after,
            "warnings": warnings,
        },
    )
    session.add(draft)
    await session.flush()
    await audit.record(
        session,
        "studio.draft",
        user_id=user.id,
        resource_type="draft",
        resource_id=str(draft.id),
        metadata={"channel": request.channel},
    )
    return DraftOut(
        id=draft.id,
        channel=draft.channel,
        recipient=draft.recipient,
        text=text,
        adjusted=adjusted,
        adjustment_note=note,
        lint=report.summary(),
        lint_after_adjustment=after,
        similarity=similarity,
        warnings=warnings,
        created_at=draft.created_at,
    )


async def get_draft(session: AsyncSession, user_id: UUID, draft_id: UUID) -> Draft:
    draft = (
        await session.execute(select(Draft).where(Draft.id == draft_id, Draft.user_id == user_id))
    ).scalar_one_or_none()
    if draft is None:
        raise NotFound("Draft not found")
    return draft


def to_out(draft: Draft) -> DraftOut:
    meta: dict[str, Any] = draft.meta or {}
    return DraftOut(
        id=draft.id,
        channel=draft.channel,
        recipient=draft.recipient,
        text=draft.final_text or draft.text,
        adjusted=bool(meta.get("adjusted")),
        lint=draft.lint,
        lint_after_adjustment=meta.get("after"),
        similarity=draft.similarity,
        warnings=list(meta.get("warnings", [])),
        created_at=draft.created_at,
    )


async def save_edit(
    session: AsyncSession, user: User, draft_id: UUID, final_text: str
) -> tuple[bool, str | None]:
    """Record the user's edited version. With consent, learn from it. Returns (learned, reason)."""
    draft = await get_draft(session, user.id, draft_id)
    draft.final_text = final_text
    await session.flush()
    if not (await consent_state(session, user.id))["fingerprint_learning"]:
        return False, "Learning from your edits is switched off."
    try:
        await fingerprint.add_sample(
            session,
            user.id,
            channel=draft.channel,
            text=final_text,
            confirm_own=True,
            origin="draft_edit",
        )
    except AppError as exc:
        return False, exc.detail
    return True, None
