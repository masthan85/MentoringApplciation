from collections.abc import Callable

import httpx
from app.core.config import Settings, get_settings
from fastapi import FastAPI


async def test_user_rate_limit(
    app: FastAPI, client: httpx.AsyncClient, auth: Callable[..., dict[str, str]], settings: Settings
) -> None:
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"rate_limit_per_user": 3}
    )
    headers = auth(sub="busy")
    statuses = [(await client.get("/v1/me", headers=headers)).status_code for _ in range(5)]
    assert statuses == [200, 200, 200, 429, 429]
    # Another user is unaffected.
    assert (await client.get("/v1/me", headers=auth(sub="calm"))).status_code == 200


async def test_ip_rate_limit_applies_but_not_to_health(settings: Settings, db: object) -> None:
    from app.main import create_app

    app = create_app(settings.model_copy(update={"rate_limit_per_ip": 2}))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        codes = [(await c.get("/v1/me")).status_code for _ in range(4)]
        assert codes == [401, 401, 429, 429]
        assert (await c.get("/healthz")).status_code == 200
