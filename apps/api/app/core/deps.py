"""FastAPI dependencies shared across modules."""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.core.errors import RateLimited, Unauthorized
from app.core.logging import bind_log_context
from app.core.redis import get_redis, hit_rate_limit
from app.core.security import Principal, TokenVerifier, build_verifier
from app.modules.identity.models import User
from app.modules.identity.service import get_or_provision_user

log = logging.getLogger(__name__)

_verifier: TokenVerifier | None = None


def get_verifier(settings: Annotated[Settings, Depends(get_settings)]) -> TokenVerifier:
    global _verifier
    if _verifier is None:
        _verifier = build_verifier(settings)
    return _verifier


def reset_verifier() -> None:
    global _verifier
    _verifier = None


async def current_principal(
    request: Request, verifier: Annotated[TokenVerifier, Depends(get_verifier)]
) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Missing bearer token")
    return await verifier.verify(token.strip())


@dataclass
class RequestContext:
    """An authenticated user and a database session scoped to them."""

    session: AsyncSession
    user: User
    principal: Principal


async def request_context(
    principal: Annotated[Principal, Depends(current_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[RequestContext]:
    async with get_sessionmaker()() as session, session.begin():
        user = await get_or_provision_user(session, principal)
        bind_log_context(user_id=str(user.id))
        await _enforce_user_rate_limit(str(user.id), settings.rate_limit_per_user)
        yield RequestContext(session=session, user=user, principal=principal)


async def _enforce_user_rate_limit(user_id: str, limit: int) -> None:
    try:
        allowed, _ = await hit_rate_limit(get_redis(), f"user:{user_id}", limit)
    except Exception:
        log.warning("rate limiter unavailable", exc_info=True)
        return
    if not allowed:
        raise RateLimited("Too many requests. Please slow down.")


# Commit the transaction before the response is sent.
RequestCtx = Annotated[RequestContext, Depends(request_context, scope="function")]
