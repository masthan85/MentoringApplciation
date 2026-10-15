from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.persona.models import PersonaConfig
from app.modules.persona.registry import PackRegistry
from app.modules.persona.selection import (
    MAX_LENSES,
    ActivePersona,
    normalise_weights,
    select_persona,
)


async def get_config(session: AsyncSession, user_id: UUID) -> PersonaConfig | None:
    return (
        await session.execute(select(PersonaConfig).where(PersonaConfig.user_id == user_id))
    ).scalar_one_or_none()


async def set_config(
    session: AsyncSession,
    user_id: UUID,
    registry: PackRegistry,
    *,
    mode: str,
    lens_ids: list[str],
    weights: list[float] | None,
) -> PersonaConfig:
    if mode not in ("auto", "pinned"):
        raise AppError("mode must be auto or pinned")
    if mode == "pinned":
        if not 1 <= len(lens_ids) <= MAX_LENSES:
            raise AppError("Pin one or two lenses")
        if len(set(lens_ids)) != len(lens_ids):
            raise AppError("Lenses must be different")
        unknown = [lens for lens in lens_ids if registry.get(lens) is None]
        if unknown:
            raise AppError(f"Unknown lens: {unknown[0]}")
        if weights is not None and len(weights) != len(lens_ids):
            raise AppError("Give one weight per lens")
        if weights is not None and any(w <= 0 for w in weights):
            raise AppError("Weights must be positive")
    config = await get_config(session, user_id)
    if config is None:
        config = PersonaConfig(user_id=user_id)
        session.add(config)
    config.mode = mode
    config.lens_ids = lens_ids if mode == "pinned" else []
    config.weights = (
        list(normalise_weights(weights or [1.0] * len(lens_ids))) if mode == "pinned" else []
    )
    await session.flush()
    return config


def resolve(
    registry: PackRegistry,
    *,
    role_family: str | None,
    seniority: str | None,
    config: PersonaConfig | None,
    suggested_lens: str | None = None,
    suggestion_confidence: float = 0.0,
) -> ActivePersona:
    pinned = config is not None and config.mode == "pinned"
    return select_persona(
        registry=registry,
        role_family=role_family,
        seniority=seniority,
        pinned_lens_ids=list(config.lens_ids) if pinned and config else None,
        pinned_weights=list(config.weights) if pinned and config else None,
        suggested_lens=suggested_lens,
        suggestion_confidence=suggestion_confidence,
        threshold=get_settings().lens_switch_threshold,
    )
