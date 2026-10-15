from fastapi import APIRouter

from app.core.deps import RequestCtx
from app.modules.regions import service

router = APIRouter(tags=["regions"])


@router.get("/v1/regions")
async def list_regions(ctx: RequestCtx) -> list[dict[str, str]]:
    """The countries the product supports, with their default time zone, spelling and currency."""
    return service.listing()
