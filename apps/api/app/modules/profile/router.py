from fastapi import APIRouter

from app.core.deps import RequestCtx
from app.modules.profile import service
from app.modules.profile.schemas import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/v1/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
async def read_profile(ctx: RequestCtx) -> ProfileOut:
    profile = await service.get_or_create_profile(ctx.session, ctx.user)
    return service.to_out(profile)


@router.put("", response_model=ProfileOut)
async def update_profile(body: ProfileUpdate, ctx: RequestCtx) -> ProfileOut:
    profile = await service.update_profile(ctx.session, ctx.user, body)
    return service.to_out(profile)
