import httpx
from app.core.redis import set_redis


async def test_healthz(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


async def test_readyz_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_readyz_reports_redis_down(client: httpx.AsyncClient) -> None:
    class Broken:
        async def ping(self) -> None:
            raise ConnectionError("down")

        def pipeline(self, **_: object) -> object:
            raise ConnectionError("down")

    set_redis(Broken())  # type: ignore[arg-type]
    response = await client.get("/readyz")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["redis"] == "unavailable"
    assert body["checks"]["database"] == "ok"


async def test_request_id_is_echoed(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={"x-request-id": "trace-me"})
    assert response.headers["x-request-id"] == "trace-me"
