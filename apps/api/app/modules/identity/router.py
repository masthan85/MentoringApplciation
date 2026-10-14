from app.core.deps import RequestCtx
from app.modules.identity.schemas import MeResponse
from fastapi import APIRouter

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
