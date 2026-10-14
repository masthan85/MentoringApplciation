"""Development-only login. Mounted only when AUTH_MODE=dev (never in staging or production)."""

import time

import jwt
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.core.config import get_settings

router = APIRouter(prefix="/v1/dev", tags=["dev"])


class DevLogin(BaseModel):
    email: EmailStr


@router.post("/login")
async def dev_login(body: DevLogin) -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": f"dev|{body.email.lower()}",
            "email": body.email.lower(),
            "exp": int(time.time()) + 12 * 3600,
        },
        settings.dev_auth_secret.get_secret_value(),
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}
