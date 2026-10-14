from collections.abc import Callable
from typing import Any

import httpx
import pytest
from app.core.db import session_scope
from app.modules.memory import service
from app.modules.memory.retrieval import rank_memories
from app.modules.memory.service import Candidate, similarity
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]


async def _user_id(client: httpx.AsyncClient, headers: dict[str, str]) -> Any:
    from uuid import UUID

    return UUID((await client.get("/v1/me", headers=headers)).json()["id"])


async def _save(
    uid: Any, content: str, type_: str = "goal_context", sensitivity: str = "normal"
) -> Any:
    async with session_scope(uid) as session:
        return await service.save_candidate(
            session,
            uid,
            Candidate(type_, content, 0.9, sensitivity),
            source_message_id=None,
            source_conversation_id=None,
        )


async def test_list_edit_delete(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    uid = await _user_id(client, h)
    memory = await _save(uid, "Wants to move into data architecture within two years")
    listed = (await client.get("/v1/memories", headers=h)).json()
    assert [m["content"] for m in listed] == [
        "Wants to move into data architecture within two years"
    ]
    edited = await client.patch(
        f"/v1/memories/{memory.id}",
        json={"content": "Wants to become a data architect by 2028", "type": "decision"},
        headers=h,
    )
    assert edited.json()["type"] == "decision" and "2028" in edited.json()["content"]
    assert (
        await client.patch(f"/v1/memories/{memory.id}", json={"type": "nonsense"}, headers=h)
    ).status_code == 400
    assert (await client.patch(f"/v1/memories/{memory.id}", json={}, headers=h)).status_code == 400
    assert (await client.delete(f"/v1/memories/{memory.id}", headers=h)).status_code == 204
    assert (await client.get("/v1/memories", headers=h)).json() == []
    assert (await client.delete(f"/v1/memories/{memory.id}", headers=h)).status_code == 404


async def test_delete_everything_needs_confirmation(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    uid = await _user_id(client, h)
    await _save(uid, "Prefers short written updates over meetings", "preference")
    await _save(uid, "Is migrating the warehouse to a lakehouse", "project")
    assert (await client.delete("/v1/memories", headers=h)).status_code == 400
    assert (await client.delete("/v1/memories?all=true", headers=h)).json() == {"deleted": 2}
    assert (await client.get("/v1/memories", headers=h)).json() == []


async def test_memories_are_private_between_users(client: httpx.AsyncClient, auth: Headers) -> None:
    a, b = auth(sub="a"), auth(sub="b")
    memory = await _save(await _user_id(client, a), "Is considering leaving their current employer")
    await _user_id(client, b)
    assert (await client.get("/v1/memories", headers=b)).json() == []
    assert (
        await client.patch(f"/v1/memories/{memory.id}", json={"content": "tampered"}, headers=b)
    ).status_code == 404
    assert (await client.delete(f"/v1/memories/{memory.id}", headers=b)).status_code == 404
    assert len((await client.get("/v1/memories", headers=a)).json()) == 1


async def test_near_duplicates_update_instead_of_multiplying(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    uid = await _user_id(client, auth())
    first = await _save(uid, "Wants to move into data architecture within two years")
    second = await _save(uid, "Wants to move into data architecture in two years")
    assert first.id == second.id
    await _save(uid, "Wants to improve stakeholder communication", "improvement_area")
    async with session_scope(uid) as session:
        assert len(await service.list_memories(session, uid)) == 2
    assert (
        similarity("plan the migration", "plan the migration") == 1.0 and similarity("", "x") == 0.0
    )


async def test_sensitive_memories_are_dropped_without_consent(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    uid = await _user_id(client, h)
    assert (
        await _save(
            uid,
            "Is dealing with a health condition that limits travel",
            "goal_context",
            "sensitive",
        )
        is None
    )
    assert (await client.get("/v1/memories", headers=h)).json() == []


async def test_sensitive_memories_are_encrypted_pending_and_confirmable(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth()
    uid = await _user_id(client, h)
    await client.put("/v1/consents/sensitive_memory", json={"granted": True}, headers=h)
    secret = "Is caring for a parent, which limits evening availability"
    memory = await _save(uid, secret, "goal_context", "sensitive")
    assert memory.status == "pending"

    async with db.connect() as conn:  # as the owner, looking at the raw row
        row = (await conn.execute(text("SELECT content, content_encrypted FROM memories"))).one()
    assert row.content == ""
    assert secret.encode() not in bytes(row.content_encrypted)

    shown = (await client.get("/v1/memories?status=pending", headers=h)).json()
    assert shown[0]["content"] == secret and shown[0]["sensitivity"] == "sensitive"
    confirmed = (await client.post(f"/v1/memories/{memory.id}/confirm", headers=h)).json()
    assert confirmed["status"] == "active"
    edited = (
        await client.patch(
            f"/v1/memories/{memory.id}", json={"content": "Cares for a parent"}, headers=h
        )
    ).json()
    assert edited["content"] == "Cares for a parent"
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT content FROM memories"))).scalar_one() == ""


async def test_database_refuses_sensitive_text_in_the_plain_column(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    from sqlalchemy.exc import DBAPIError

    uid = await _user_id(client, auth())
    with pytest.raises(DBAPIError):
        async with session_scope(uid) as session:
            await session.execute(
                text(
                    "INSERT INTO memories (user_id, type, content, sensitivity) "
                    "VALUES (:u, 'goal_context', 'plain secret', 'sensitive')"
                ),
                {"u": uid},
            )


async def test_export_json_and_markdown(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth()
    uid = await _user_id(client, h)
    await client.put(
        "/v1/profile", json={"role_family": "data_architect", "stack": ["Databricks"]}, headers=h
    )
    await _save(uid, "Wants to present at a conference this year", "goal_context")
    exported = await client.get("/v1/memories/export", headers=h)
    assert exported.headers["content-disposition"].endswith('mentor-notes.json"')
    document = exported.json()
    assert document["profile"]["role_family"] == "data_architect"
    assert [m["content"] for m in document["memories"]] == [
        "Wants to present at a conference this year"
    ]
    assert document["consents"]["sensitive_memory"] is False
    md = await client.get("/v1/memories/export?format=markdown", headers=h)
    assert md.headers["content-type"].startswith("text/markdown")
    assert (
        "# My mentor's notes" in md.text and "Wants to present at a conference this year" in md.text
    )
    assert "Databricks" in md.text
    async with db.connect() as conn:
        actions = (
            await conn.execute(
                text("SELECT action FROM audit_events WHERE action = 'memory.export'")
            )
        ).all()
    assert len(actions) == 2


async def test_retrieval_prefers_commitments_goals_and_overlap(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    uid = await _user_id(client, auth())
    await _save(uid, "Likes dark mode in editors", "preference")
    await _save(uid, "Will present the lineage proposal to the CTO on Friday", "commitment")
    await _save(uid, "Is working on Unity Catalog governance", "project")
    async with session_scope(uid) as session:
        rows = await service.list_memories(session, uid)
    ranked = [text for _, text in rank_memories(rows, "how do I explain Unity Catalog governance?")]
    assert ranked[0] == "Is working on Unity Catalog governance" or ranked[0].startswith(
        "Will present"
    )
    assert ranked[-1] == "Likes dark mode in editors"
    assert rank_memories(rows, "x", budget_tokens=10) == []  # the budget is honoured
    assert [m.status for m, _ in rank_memories(rows, "")] == ["active"] * 3
