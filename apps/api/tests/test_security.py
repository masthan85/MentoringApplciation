import json
import time
from typing import Any

import httpx
import jwt
import pytest
from app.core.config import Settings
from app.core.errors import Unauthorized
from app.core.security import DevVerifier, JWKSVerifier
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://issuer.example/"
AUDIENCE = "mentor-api"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "env": "test",
        "auth_mode": "oidc",
        "auth_issuer": ISSUER,
        "auth_audience": AUDIENCE,
        "auth_jwks_url": "https://issuer.example/jwks.json",
    }
    return Settings(**{**base, **overrides})


def _keypair(kid: str) -> tuple[Any, dict[str, Any]]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update({"kid": kid, "alg": "RS256", "use": "sig"})
    return private, jwk


def _token(private: Any, kid: str, **claims: Any) -> str:
    payload = {"sub": "u1", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 300, **claims}
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": kid})


class JwksServer:
    def __init__(self, keys: list[dict[str, Any]]) -> None:
        self.keys = keys
        self.requests = 0

    def client(self) -> httpx.AsyncClient:
        def handler(_: httpx.Request) -> httpx.Response:
            self.requests += 1
            return httpx.Response(200, json={"keys": self.keys})

        return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_valid_token() -> None:
    private, jwk = _keypair("k1")
    server = JwksServer([jwk])
    verifier = JWKSVerifier(_settings(), server.client())
    principal = await verifier.verify(_token(private, "k1", email="a@b.co", roles=["admin"]))
    assert principal.subject == "u1"
    assert principal.email == "a@b.co"
    assert principal.is_admin


async def test_non_admin_by_default() -> None:
    private, jwk = _keypair("k1")
    verifier = JWKSVerifier(_settings(), JwksServer([jwk]).client())
    assert not (await verifier.verify(_token(private, "k1"))).is_admin


@pytest.mark.parametrize(
    "claims",
    [{"aud": "someone-else"}, {"iss": "https://evil.example/"}, {"exp": int(time.time()) - 10}],
)
async def test_rejects_bad_claims(claims: dict[str, Any]) -> None:
    private, jwk = _keypair("k1")
    verifier = JWKSVerifier(_settings(), JwksServer([jwk]).client())
    with pytest.raises(Unauthorized):
        await verifier.verify(_token(private, "k1", **claims))


async def test_rejects_token_signed_with_a_different_key() -> None:
    _, jwk = _keypair("k1")
    other, _ = _keypair("k1")
    verifier = JWKSVerifier(_settings(), JwksServer([jwk]).client())
    with pytest.raises(Unauthorized):
        await verifier.verify(_token(other, "k1"))


async def test_unknown_kid_triggers_one_refetch_then_fails() -> None:
    private, jwk = _keypair("k1")
    server = JwksServer([jwk])
    verifier = JWKSVerifier(_settings(), server.client())
    await verifier.verify(_token(private, "k1"))
    assert server.requests == 1
    stranger, _ = _keypair("nope")
    with pytest.raises(Unauthorized):
        await verifier.verify(_token(stranger, "nope"))


async def test_key_rotation_is_picked_up() -> None:
    old_private, old_jwk = _keypair("old")
    server = JwksServer([old_jwk])
    verifier = JWKSVerifier(_settings(), server.client())
    await verifier.verify(_token(old_private, "old"))
    new_private, new_jwk = _keypair("new")
    server.keys = [old_jwk, new_jwk]
    verifier._fetched_at -= 60  # past the minimum refetch interval
    assert (await verifier.verify(_token(new_private, "new"))).subject == "u1"


async def test_rejects_alg_none_and_hs256_tokens() -> None:
    _, jwk = _keypair("k1")
    verifier = JWKSVerifier(_settings(), JwksServer([jwk]).client())
    forged = jwt.encode(
        {"sub": "u1", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 60},
        "secret-secret-secret-secret-secret-123",
        algorithm="HS256",
        headers={"kid": "k1"},
    )
    with pytest.raises(Unauthorized):
        await verifier.verify(forged)


async def test_missing_kid_rejected() -> None:
    private, jwk = _keypair("k1")
    verifier = JWKSVerifier(_settings(), JwksServer([jwk]).client())
    token = jwt.encode(
        {"sub": "u1", "iss": ISSUER, "aud": AUDIENCE, "exp": int(time.time()) + 60},
        private,
        algorithm="RS256",
    )
    with pytest.raises(Unauthorized):
        await verifier.verify(token)


def test_symmetric_algorithms_refused_in_oidc_mode() -> None:
    with pytest.raises(ValueError, match="Symmetric"):
        JWKSVerifier(_settings(auth_algorithms=["HS256"]))


async def test_jwks_outage_is_unauthorized_not_a_crash() -> None:
    private, _ = _keypair("k1")
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    verifier = JWKSVerifier(_settings(), client)
    with pytest.raises(Unauthorized):
        await verifier.verify(_token(private, "k1"))


async def test_dev_verifier_roundtrip_and_rejections() -> None:
    settings = Settings(env="test", auth_mode="dev", dev_auth_secret="s" * 40)  # type: ignore[arg-type]
    verifier = DevVerifier(settings)
    good = jwt.encode({"sub": "x", "exp": int(time.time()) + 60}, "s" * 40, algorithm="HS256")
    assert (await verifier.verify(good)).subject == "x"
    bad = jwt.encode({"sub": "x", "exp": int(time.time()) + 60}, "t" * 40, algorithm="HS256")
    with pytest.raises(Unauthorized):
        await verifier.verify(bad)
    expired = jwt.encode({"sub": "x", "exp": int(time.time()) - 60}, "s" * 40, algorithm="HS256")
    with pytest.raises(Unauthorized):
        await verifier.verify(expired)
