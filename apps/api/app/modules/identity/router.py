from fastapi import APIRouter
from pydantic import BaseModel

from app.core.deps import RequestCtx
from app.core.errors import NotFound
from app.modules.identity import service
from app.modules.identity.schemas import MeResponse

router = APIRouter(prefix="/v1", tags=["identity"])


@router.get("/me", response_model=MeResponse)
async def read_me(ctx: RequestCtx) -> MeResponse:
    return MeResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        display_name=ctx.user.display_name,
        is_admin=ctx.principal.is_admin,
        created_at=ctx.user.created_at,
    )


class ConsentIn(BaseModel):
    granted: bool


@router.get("/consents", response_model=dict[str, bool])
async def read_consents(ctx: RequestCtx) -> dict[str, bool]:
    return await service.consent_state(ctx.session, ctx.user.id)


@router.put("/consents/{purpose}", response_model=dict[str, bool])
async def put_consent(purpose: str, body: ConsentIn, ctx: RequestCtx) -> dict[str, bool]:
    if purpose not in service.CONSENT_PURPOSES:
        raise NotFound("Unknown consent purpose")
    await service.set_consent(ctx.session, ctx.user, purpose, body.granted)
    return await service.consent_state(ctx.session, ctx.user.id)
