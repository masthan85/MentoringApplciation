"""Writing samples (encrypted) and the style profile derived from them."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import AppError, NotFound
from app.modules.audit import service as audit
from app.modules.fingerprint import features as fx
from app.modules.fingerprint.card import describe
from app.modules.fingerprint.models import StyleProfile, WritingSample
from app.modules.voice.lint import load_config
from app.modules.voice.text import words

MIN_SAMPLE_WORDS = 30
MAX_SAMPLE_WORDS = 3000
MAX_SAMPLES = 60
EXEMPLAR_LIMIT = 3


@dataclass(frozen=True)
class FingerprintContext:
    summary: str | None = None
    exemplars: tuple[str, ...] = ()
    baseline_cv: float | None = None
    features: dict[str, Any] | None = None


def valid_channels() -> list[str]:
    channels: dict[str, Any] = load_config()["channels"]
    return list(channels)


async def add_sample(
    session: AsyncSession,
    user_id: UUID,
    *,
    channel: str,
    text: str,
    confirm_own: bool,
    origin: str = "user_provided",
) -> WritingSample:
    if channel not in valid_channels():
        raise AppError("Unknown channel")
    if origin == "user_provided" and not confirm_own:
        raise AppError(
            "Please confirm that you wrote this yourself. Other people's writing is never used."
        )
    count = len(words(text))
    if count < MIN_SAMPLE_WORDS:
        raise AppError(
            f"Please give at least {MIN_SAMPLE_WORDS} words so there is something to learn from."
        )
    if count > MAX_SAMPLE_WORDS:
        raise AppError(f"That is too long. Please keep samples under {MAX_SAMPLE_WORDS} words.")
    total = (
        await session.execute(
            select(func.count()).select_from(WritingSample).where(WritingSample.user_id == user_id)
        )
    ).scalar_one()
    if total >= MAX_SAMPLES:
        raise AppError("You have reached the limit of saved samples. Delete some to add more.")
    sample = WritingSample(
        user_id=user_id,
        channel=channel,
        text_encrypted=crypto.encrypt(text.strip()),
        word_count=count,
        origin=origin,
    )
    session.add(sample)
    await session.flush()
    await recompute_profile(session, user_id)
    await audit.record(
        session,
        "fingerprint.sample_added",
        user_id=user_id,
        resource_type="writing_sample",
        resource_id=str(sample.id),
        metadata={"origin": origin, "channel": channel},
    )
    return sample


async def list_samples(session: AsyncSession, user_id: UUID) -> list[WritingSample]:
    rows = await session.execute(
        select(WritingSample)
        .where(WritingSample.user_id == user_id)
        .order_by(WritingSample.created_at.desc())
    )
    return list(rows.scalars())


def sample_text(sample: WritingSample) -> str:
    return crypto.decrypt(sample.text_encrypted)


async def delete_sample(session: AsyncSession, user_id: UUID, sample_id: UUID) -> None:
    sample = (
        await session.execute(
            select(WritingSample).where(
                WritingSample.id == sample_id, WritingSample.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if sample is None:
        raise NotFound("Sample not found")
    await session.delete(sample)
    await session.flush()
    await recompute_profile(session, user_id)
    await audit.record(
        session,
        "fingerprint.sample_deleted",
        user_id=user_id,
        resource_type="writing_sample",
        resource_id=str(sample_id),
    )


async def get_profile(session: AsyncSession, user_id: UUID) -> StyleProfile | None:
    return (
        await session.execute(select(StyleProfile).where(StyleProfile.user_id == user_id))
    ).scalar_one_or_none()


async def recompute_profile(session: AsyncSession, user_id: UUID) -> StyleProfile | None:
    """Rebuild the fingerprint from every stored sample, per channel and overall."""
    samples = await list_samples(session, user_id)
    profile = await get_profile(session, user_id)
    if not samples:
        if profile is not None and profile.voice_card_override is None:
            await session.delete(profile)
        elif profile is not None:
            profile.features, profile.voice_cards, profile.sample_count = {}, {}, 0
        await session.flush()
        return None
    by_channel: dict[str, list[str]] = {}
    for sample in samples:
        by_channel.setdefault(sample.channel, []).append(sample_text(sample))
    all_features: dict[str, Any] = {
        "overall": fx.compute_features(
            "\n\n".join(t for texts in by_channel.values() for t in texts)
        )
    }
    for channel, texts in by_channel.items():
        all_features[channel] = fx.compute_features("\n\n".join(texts))
    cards = {name: card for name, feats in all_features.items() if (card := describe(feats))}
    if profile is None:
        profile = StyleProfile(user_id=user_id)
        session.add(profile)
    profile.features = all_features
    profile.voice_cards = cards
    profile.sample_count = len(samples)
    await session.flush()
    return profile


async def delete_profile(session: AsyncSession, user_id: UUID) -> int:
    """Delete the fingerprint as one unit: the profile and every sample behind it."""
    result = await session.execute(delete(WritingSample).where(WritingSample.user_id == user_id))
    count: int = result.rowcount  # type: ignore[attr-defined]
    await session.execute(delete(StyleProfile).where(StyleProfile.user_id == user_id))
    await audit.record(
        session,
        "fingerprint.deleted",
        user_id=user_id,
        resource_type="style_profile",
        metadata={"samples": count},
    )
    return count


async def set_override(session: AsyncSession, user_id: UUID, text: str | None) -> StyleProfile:
    profile = await get_profile(session, user_id)
    if profile is None:
        profile = StyleProfile(user_id=user_id, features={}, voice_cards={}, sample_count=0)
        session.add(profile)
    profile.voice_card_override = text.strip() if text and text.strip() else None
    await session.flush()
    return profile


async def context_for(session: AsyncSession, user_id: UUID, channel: str) -> FingerprintContext:
    profile = await get_profile(session, user_id)
    if profile is None:
        return FingerprintContext()
    feats: dict[str, Any] = profile.features.get(channel) or profile.features.get("overall") or {}
    summary = (
        profile.voice_card_override
        or profile.voice_cards.get(channel)
        or profile.voice_cards.get("overall")
    )
    exemplars: list[str] = []
    for sample in await list_samples(session, user_id):
        if sample.channel == channel and len(exemplars) < EXEMPLAR_LIMIT:
            exemplars.append(sample_text(sample))
    cv = feats.get("sentence_cv") if not feats.get("insufficient") else None
    return FingerprintContext(summary, tuple(exemplars), cv, feats or None)


async def similarity_to(
    session: AsyncSession, user_id: UUID, channel: str, text: str
) -> float | None:
    profile = await get_profile(session, user_id)
    if profile is None:
        return None
    reference = profile.features.get(channel) or profile.features.get("overall")
    if not reference:
        return None
    return fx.similarity(fx.compute_features(text, fx.MIN_WORDS_TO_SCORE), reference)
