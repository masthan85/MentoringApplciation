"""Onboarding: a guided conversation that fills in the profile."""

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.llm_gateway import CompletionRequest, LLMError, Message, current_gateway
from app.modules.llm_gateway.structured import parse_structured
from app.modules.orchestration.context import (
    ONBOARDING,
    SAFETY,
    PromptBundle,
    approx_tokens,
    trim_history,
)
from app.modules.profile.models import Profile
from app.modules.profile.service import missing_fields
from app.modules.profile.taxonomy import RoleFamily, Seniority
from app.modules.regions import service as regions
from app.modules.regions.service import codes as region_codes
from app.prompts import registry as prompts

log = logging.getLogger(__name__)
EXTRACTION = ("profile_extraction", 2)

NEEDED_LABELS = {
    "role_family": "what they do (their role)",
    "country": "which country they work in (UK, Ireland, US, Canada or India)",
    "seniority": "their level of seniority",
    "stack": "the tools and technologies they use",
    "goals_summary": "what they want from mentoring or their career",
    "current_challenge": "the main challenge they face right now",
}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "role_family",
        "seniority",
        "job_title",
        "years_experience",
        "country",
        "stack",
        "goals_summary",
        "current_challenge",
    ],
    "properties": {
        "role_family": {"type": "string", "enum": [*[r.value for r in RoleFamily], "unknown"]},
        "seniority": {"type": "string", "enum": [*[s.value for s in Seniority], "unknown"]},
        "job_title": {"type": "string"},
        "years_experience": {"type": "integer"},
        "country": {"type": "string", "enum": [*region_codes(), "other", "unknown"]},
        "stack": {"type": "array", "items": {"type": "string"}},
        "goals_summary": {"type": "string"},
        "current_challenge": {"type": "string"},
    },
}


class ProfileDraft(BaseModel):
    role_family: Literal[
        "data_engineer",
        "data_architect",
        "analytics_engineer",
        "ml_ai_engineer",
        "software_engineer",
        "tech_lead",
        "engineering_manager",
        "other",
        "unknown",
    ] = "unknown"
    seniority: Literal["junior", "mid", "senior", "lead", "executive", "unknown"] = "unknown"
    job_title: str = ""
    country: str = "unknown"
    years_experience: int = Field(default=-1)
    stack: list[str] = Field(default_factory=list)
    goals_summary: str = ""
    current_challenge: str = ""


def merge_draft(profile: Profile, draft: ProfileDraft) -> list[str]:
    """Apply what was extracted. Empty and unknown values never overwrite what is known."""
    changed: list[str] = []

    def set_if(name: str, value: object) -> None:
        if value not in (None, "", [], "unknown", -1) and getattr(profile, name) != value:
            setattr(profile, name, value)
            changed.append(name)

    set_if("role_family", draft.role_family)
    set_if("seniority", draft.seniority)
    set_if("job_title", draft.job_title.strip()[:120])
    if draft.country in region_codes() and profile.country != draft.country:
        profile.country = draft.country
        changed.append("country")
        region = regions.get(draft.country)
        if region is not None:
            # Only fill in what the user has not already chosen.
            profile.timezone = profile.timezone or region.timezone
            if profile.english_variant == "en-GB" and region.english_variant != "en-GB":
                profile.english_variant = region.english_variant
    if 0 <= draft.years_experience <= 60:
        set_if("years_experience", draft.years_experience)
    set_if("goals_summary", draft.goals_summary.strip()[:2000])
    set_if("current_challenge", draft.current_challenge.strip()[:2000])
    if draft.stack:
        merged = list(profile.stack or [])
        known = {s.lower() for s in merged}
        for item in draft.stack:
            clean = item.strip()[:60]
            if clean and clean.lower() not in known and len(merged) < 20:
                merged.append(clean)
                known.add(clean.lower())
        if merged != list(profile.stack or []):
            profile.stack = merged
            changed.append("stack")
    return changed


async def extract_profile(history: list[Message]) -> ProfileDraft | None:
    transcript = "\n".join(f"<{m.role}>{m.content[:1500]}</{m.role}>" for m in history[-14:])
    try:
        result = await current_gateway().complete(
            "classifier",
            CompletionRequest(
                system=prompts.load(*EXTRACTION),
                messages=[Message("user", f"<conversation>\n{transcript}\n</conversation>")],
                response_schema=SCHEMA,
                tags={"purpose": "profile_extraction"},
            ),
        )
    except LLMError:
        log.warning("profile extraction unavailable", exc_info=True)
        return None
    return parse_structured(result.text, ProfileDraft)


def build_onboarding_prompt(profile: Profile, history: list[Message]) -> PromptBundle:
    known = []
    for name in (
        "role_family",
        "seniority",
        "job_title",
        "country",
        "years_experience",
        "stack",
        "goals_summary",
        "current_challenge",
    ):
        value = getattr(profile, name)
        if value not in (None, "", []):
            known.append(
                f"- {name.replace('_', ' ')}: {', '.join(value) if isinstance(value, list) else value}"
            )
    still = [NEEDED_LABELS[name] for name in missing_fields(profile)]
    progress = (
        "Already known about the user:\n"
        + ("\n".join(known) if known else "- nothing yet")
        + "\n\n"
        + (
            "Still to learn (ask about the first of these next, naturally): " + "; ".join(still)
            if still
            else "You now have everything needed. Say so briefly and invite them to check and confirm the profile card."
        )
    )
    system = "\n\n".join([prompts.load(*SAFETY), prompts.load(*ONBOARDING), progress])
    return PromptBundle(
        system=system,
        messages=trim_history(history),
        section_tokens={"onboarding": approx_tokens(system)},
        prompt_versions={
            "safety_policy": prompts.version_label(*SAFETY),
            "onboarding": prompts.version_label(*ONBOARDING),
        },
    )
