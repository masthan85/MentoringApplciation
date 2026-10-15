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
    email = body.email.lower()
    claims: dict[str, object] = {
        "sub": f"dev|{email}",
        "email": email,
        "exp": int(time.time()) + 12 * 3600,
    }
    if email in {e.lower() for e in settings.dev_admin_emails}:
        claims[settings.auth_admin_claim] = [settings.auth_admin_role]
    token = jwt.encode(claims, settings.dev_auth_secret.get_secret_value(), algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}
