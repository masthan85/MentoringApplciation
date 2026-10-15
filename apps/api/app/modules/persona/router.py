from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import RequestCtx
from app.modules.persona import service
from app.modules.persona.registry import PackRegistry, get_registry
from app.modules.profile.service import get_or_create_profile

router = APIRouter(prefix="/v1/personas", tags=["personas"])
Registry = Annotated[PackRegistry, Depends(get_registry)]


class LensOut(BaseModel):
    id: str
    name: str
    domain: str
    pack: str
    summary: str


class ActiveOut(BaseModel):
    mode: str
    lens_ids: list[str]
    weights: list[float]
    names: list[str]
    source: str


class ActiveIn(BaseModel):
    mode: str = "auto"
    lens_ids: list[str] = Field(default_factory=list, max_length=2)
    weights: list[float] | None = None


@router.get("", response_model=list[LensOut])
async def list_lenses(_: RequestCtx, registry: Registry) -> list[LensOut]:
    out = []
    for pack in registry.packs.values():
        for lens in pack.lenses:
            out.append(
                LensOut(
                    id=lens.id,
                    name=lens.name,
                    domain=lens.domain,
                    pack=pack.pack.name,
                    summary=lens.perspective,
                )
            )
    return out


async def _active(ctx: RequestCtx, registry: PackRegistry) -> ActiveOut:
    profile = await get_or_create_profile(ctx.session, ctx.user)
    config = await service.get_config(ctx.session, ctx.user.id)
    persona = service.resolve(
        registry, role_family=profile.role_family, seniority=profile.seniority, config=config
    )
    names = [lens.name for lid in persona.lens_ids if (lens := registry.get(lid))]
    return ActiveOut(
        mode=config.mode if config else "auto",
        lens_ids=list(persona.lens_ids),
        weights=list(persona.weights),
        names=names,
        source=persona.source,
    )


@router.get("/active", response_model=ActiveOut)
async def get_active(ctx: RequestCtx, registry: Registry) -> ActiveOut:
    return await _active(ctx, registry)


@router.put("/active", response_model=ActiveOut)
async def set_active(body: ActiveIn, ctx: RequestCtx, registry: Registry) -> ActiveOut:
    await service.set_config(
        ctx.session,
        ctx.user.id,
        registry,
        mode=body.mode,
        lens_ids=body.lens_ids,
        weights=body.weights,
    )
    return await _active(ctx, registry)
