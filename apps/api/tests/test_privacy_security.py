import json
from collections.abc import Callable

import httpx
from app.core.config import Settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]


async def test_export_contains_the_users_data_and_not_anyone_elses(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    a, b = auth(sub="a", email="a@example.com"), auth(sub="b", email="b@example.com")
    levels = {"minus_two": "1", "minus_one": "2", "zero": "3", "plus_one": "4", "plus_two": "5"}
    await client.post("/v1/goals", json={"title": "Goal for A", "levels": levels}, headers=a)
    await client.post("/v1/goals", json={"title": "Goal for B", "levels": levels}, headers=b)
    r = await client.get("/v1/privacy/export", headers=a)
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    document = json.loads(r.text)
    assert [g["title"] for g in document["goals"]] == ["Goal for A"]
    assert "Goal for B" not in r.text
    assert "token_hash" not in r.text and "embedding" not in r.text
    assert document["account"]["email"] == "a@example.com"


async def test_deleting_an_account_needs_the_phrase_and_removes_everything(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth(sub="gone", email="gone@example.com")
    levels = {"minus_two": "1", "minus_one": "2", "zero": "3", "plus_one": "4", "plus_two": "5"}
    await client.post("/v1/goals", json={"title": "Temporary", "levels": levels}, headers=h)
    await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)

    wrong = await client.post("/v1/privacy/delete-account", json={"confirm": "yes"}, headers=h)
    assert wrong.status_code == 400

    ok = await client.post(
        "/v1/privacy/delete-account", json={"confirm": "Delete my account"}, headers=h
    )
    assert ok.status_code == 204
    async with db.connect() as conn:
        for table in ("users", "goals", "conversations", "profiles", "consents"):
            count = (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()  # noqa: S608
            assert count == 0, table
        deleted = (
            await conn.execute(
                text("SELECT count(*) FROM audit_events WHERE action = 'account.deleted'")
            )
        ).scalar_one()
        assert deleted == 1
        linked = (
            await conn.execute(text("SELECT count(*) FROM audit_events WHERE user_id IS NOT NULL"))
        ).scalar_one()
        assert linked == 0


async def test_the_access_log_shows_only_the_users_own_events(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    a, b = auth(sub="a", email="a@example.com"), auth(sub="b", email="b@example.com")
    await client.get("/v1/memories/export", headers=a)
    await client.get("/v1/memories/export", headers=b)
    log = (await client.get("/v1/privacy/access-log", headers=a)).json()
    assert [e["action"] for e in log].count("memory.export") == 1
    assert all(e["by"] == "you" for e in log)


async def test_the_admin_audit_view_is_admin_only_and_itself_audited(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    user = auth(sub="u", email="u@example.com")
    admin = auth(sub="admin", email="admin@example.com", roles=["admin"])
    await client.get("/v1/memories/export", headers=user)
    assert (await client.get("/v1/admin/audit", headers=user)).status_code == 403
    rows = (await client.get("/v1/admin/audit?action=memory.export", headers=admin)).json()
    assert len(rows) == 1
    again = (await client.get("/v1/admin/audit?action=admin.audit_viewed", headers=admin)).json()
    assert len(again) >= 1


async def test_responses_carry_security_headers(client: httpx.AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert "strict-transport-security" not in r.headers  # only behind HTTPS in staging/production


async def test_oversized_bodies_are_refused(
    client: httpx.AsyncClient, auth: Headers, settings: Settings
) -> None:
    big = "x" * (settings.max_body_bytes + 10)
    r = await client.post(
        "/v1/goals", content=big, headers={**auth(), "content-type": "application/json"}
    )
    assert r.status_code == 413
    assert r.headers["x-frame-options"] == "DENY"
