"""Token verification. The identity provider is a plug-in, not a dependency.

``JWKSVerifier`` works with any OIDC provider that publishes a JWKS (Auth0,
Clerk, Microsoft Entra External ID). ``DevVerifier`` is for local work and is
refused by settings validation outside local and test environments.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt

from app.core.config import Settings
from app.core.errors import Unauthorized

_JWKS_TTL_S = 600
_JWKS_MIN_REFETCH_S = 30


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str | None
    is_admin: bool


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


def _principal_from_claims(claims: dict[str, Any], settings: Settings) -> Principal:
    roles = claims.get(settings.auth_admin_claim) or []
    if isinstance(roles, str):
        roles = [roles]
    email = claims.get("email")
    return Principal(
        subject=str(claims["sub"]),
        email=email if isinstance(email, str) else None,
        is_admin=settings.auth_admin_role in roles,
    )


class DevVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._settings.dev_auth_secret.get_secret_value(),
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise Unauthorized("Invalid or expired token") from exc
        return _principal_from_claims(claims, self._settings)


class JWKSVerifier:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if not (settings.auth_issuer and settings.auth_audience and settings.auth_jwks_url):
            raise ValueError("issuer, audience and jwks url are required")
        if any(
            alg.upper().startswith("HS") or alg.lower() == "none"
            for alg in settings.auth_algorithms
        ):
            raise ValueError("Symmetric or unsigned algorithms are not allowed in oidc mode")
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=5.0)
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh(self, *, force: bool) -> None:
        async with self._lock:
            age = time.monotonic() - self._fetched_at
            if self._keys and age < (_JWKS_MIN_REFETCH_S if force else _JWKS_TTL_S):
                return
            assert self._settings.auth_jwks_url
            response = await self._client.get(self._settings.auth_jwks_url)
            response.raise_for_status()
            keys: dict[str, jwt.PyJWK] = {}
            for entry in response.json().get("keys", []):
                if "kid" in entry:
                    keys[entry["kid"]] = jwt.PyJWK.from_dict(entry)
            self._keys = keys
            self._fetched_at = time.monotonic()

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        try:
            await self._refresh(force=False)
            if kid not in self._keys:
                await self._refresh(force=True)  # key rotation
        except httpx.HTTPError as exc:
            raise Unauthorized("Unable to verify token right now") from exc
        key = self._keys.get(kid)
        if key is None:
            raise Unauthorized("Unknown signing key")
        return key

    async def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise Unauthorized("Token has no key id")
            key = await self._key_for(kid)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=self._settings.auth_algorithms,
                audience=self._settings.auth_audience,
                issuer=self._settings.auth_issuer,
                options={"require": ["exp", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise Unauthorized("Invalid or expired token") from exc
        return _principal_from_claims(claims, self._settings)


def build_verifier(settings: Settings) -> TokenVerifier:
    if settings.auth_mode == "dev":
        return DevVerifier(settings)
    return JWKSVerifier(settings)
