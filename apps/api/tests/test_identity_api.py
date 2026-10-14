from collections.abc import Callable

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_requires_a_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["request_id"]


async def test_rejects_a_bad_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


async def test_rejects_wrong_scheme(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/me", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


async def test_first_sign_in_provisions_user_and_audits(
    client: httpx.AsyncClient, auth: Callable[..., dict[str, str]], db: AsyncEngine
) -> None:
    response = await client.get("/v1/me", headers=auth(sub="auth0|abc", email="ada@example.com"))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["is_admin"] is False

    async with db.connect() as conn:
        users = (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one()
        events = (
            (
                await conn.execute(
                    text("SELECT action FROM audit_events WHERE user_id = :u"), {"u": body["id"]}
                )
            )
            .scalars()
            .all()
        )
    assert users == 1
    assert events == ["user.provisioned"]


async def test_second_request_reuses_the_user(
    client: httpx.AsyncClient, auth: Callable[..., dict[str, str]], db: AsyncEngine
) -> None:
    headers = auth(sub="auth0|abc")
    first = (await client.get("/v1/me", headers=headers)).json()
    second = (await client.get("/v1/me", headers=headers)).json()
    assert first["id"] == second["id"]
    async with db.connect() as conn:
        events = (await conn.execute(text("SELECT count(*) FROM audit_events"))).scalar_one()
    assert events == 1


async def test_different_subjects_are_different_users(
    client: httpx.AsyncClient, auth: Callable[..., dict[str, str]]
) -> None:
    a = (await client.get("/v1/me", headers=auth(sub="a", email="a@x.co"))).json()
    b = (await client.get("/v1/me", headers=auth(sub="b", email="b@x.co"))).json()
    assert a["id"] != b["id"]


async def test_admin_role_comes_from_the_token(
    client: httpx.AsyncClient, auth: Callable[..., dict[str, str]]
) -> None:
    response = await client.get("/v1/me", headers=auth(sub="boss", roles=["admin"]))
    assert response.json()["is_admin"] is True


async def test_suspended_users_are_refused(
    client: httpx.AsyncClient, auth: Callable[..., dict[str, str]], db: AsyncEngine
) -> None:
    headers = auth(sub="s1")
    assert (await client.get("/v1/me", headers=headers)).status_code == 200
    async with db.begin() as conn:
        await conn.execute(text("UPDATE users SET status = 'suspended' WHERE auth_subject = 's1'"))
    response = await client.get("/v1/me", headers=headers)
    assert response.status_code == 403
    assert response.json()["title"] == "forbidden"


async def test_unknown_route_is_a_problem_document(client: httpx.AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
