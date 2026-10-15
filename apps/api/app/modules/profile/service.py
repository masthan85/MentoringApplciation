from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.audit import service as audit
from app.modules.identity.models import User
from app.modules.profile.models import Profile
from app.modules.profile.schemas import ProfileOut, ProfileUpdate
from app.modules.profile.taxonomy import REQUIRED_FIELDS, OnboardingStatus


def writing_modes() -> set[str]:
    """The modes defined in the Natural Voice configuration (one source of truth)."""
    from app.modules.voice.lint import load_config

    return set(load_config()["modes"])


async def get_or_create_profile(session: AsyncSession, user: User) -> Profile:
    profile = (
        await session.execute(select(Profile).where(Profile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        profile = Profile(user_id=user.id, stack=[], onboarding_status="not_started")
        session.add(profile)
        await session.flush()
    return profile


def missing_fields(profile: Profile) -> list[str]:
    missing = []
    for name in REQUIRED_FIELDS:
        value = getattr(profile, name)
        if value is None or value == "" or value == []:
            missing.append(name)
    return missing


def to_out(profile: Profile) -> ProfileOut:
    out = ProfileOut.model_validate(profile)
    out.missing_fields = missing_fields(profile)
    return out


async def update_profile(
    session: AsyncSession, user: User, update: ProfileUpdate, *, audit_event: bool = True
) -> Profile:
    profile = await get_or_create_profile(session, user)
    changes = update.model_dump(exclude_unset=True, exclude={"confirm_onboarding"})
    if "writing_mode" in changes and changes["writing_mode"] not in writing_modes():
        raise AppError("Unknown writing mode")
    for name, value in changes.items():
        if value is None and name not in ("job_title", "years_experience", "email_reminders"):
            continue  # required fields are cleared by sending an empty string or list
        setattr(profile, name, value.value if hasattr(value, "value") else value)
    if update.confirm_onboarding:
        gaps = missing_fields(profile)
        if gaps:
            raise AppError("The profile is not complete yet", extra={"missing_fields": gaps})
        profile.onboarding_status = OnboardingStatus.COMPLETE.value
    elif profile.onboarding_status == OnboardingStatus.NOT_STARTED.value and changes:
        profile.onboarding_status = OnboardingStatus.IN_PROGRESS.value
    if audit_event:
        await audit.record(
            session,
            "profile.update",
            user_id=user.id,
            resource_type="profile",
            metadata={"fields": sorted(changes)},
        )
    await session.flush()
    return profile
