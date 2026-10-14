"""Row-level security, exercised as the real runtime role (not the owner)."""

import uuid

import pytest
from app.core.db import session_scope
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine


async def _make_users(owner: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    async with owner.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    "INSERT INTO users (auth_subject, email) VALUES ('a','a@x.co'), ('b','b@x.co') "
                    "RETURNING id, auth_subject"
                )
            )
        ).all()
    by_subject = {r.auth_subject: r.id for r in rows}
    return by_subject["a"], by_subject["b"]


async def test_a_user_only_sees_their_own_row(db: AsyncEngine) -> None:
    a, b = await _make_users(db)
    async with session_scope(a) as session:
        ids = (await session.execute(text("SELECT id FROM users"))).scalars().all()
    assert ids == [a]
    async with session_scope(b) as session:
        ids = (await session.execute(text("SELECT id FROM users"))).scalars().all()
    assert ids == [b]


async def test_no_user_context_sees_nothing(db: AsyncEngine) -> None:
    await _make_users(db)
    async with session_scope(None) as session:
        assert (await session.execute(text("SELECT count(*) FROM users"))).scalar_one() == 0


async def test_cannot_update_someone_elses_row(db: AsyncEngine) -> None:
    a, b = await _make_users(db)
    async with session_scope(a) as session:
        result = await session.execute(
            text("UPDATE users SET display_name = 'hacked' WHERE id = :b"), {"b": b}
        )
        assert result.rowcount == 0  # type: ignore[attr-defined]
    async with db.connect() as conn:
        name = (
            await conn.execute(text("SELECT display_name FROM users WHERE id = :b"), {"b": b})
        ).scalar_one()
    assert name is None


async def test_runtime_role_cannot_insert_users_directly(db: AsyncEngine) -> None:
    a, _ = await _make_users(db)
    with pytest.raises(DBAPIError):
        async with session_scope(a) as session:
            await session.execute(text("INSERT INTO users (auth_subject) VALUES ('mallory')"))


async def test_consents_are_per_user_and_append_only(db: AsyncEngine) -> None:
    a, b = await _make_users(db)
    insert = text(
        "INSERT INTO consents (user_id, purpose, granted, policy_version) "
        "VALUES (:u, 'analytics', true, 'v1')"
    )
    async with session_scope(a) as session:
        await session.execute(insert, {"u": a})
    with pytest.raises(DBAPIError):  # cannot record consent on behalf of another user
        async with session_scope(a) as session:
            await session.execute(insert, {"u": b})
    async with session_scope(b) as session:
        assert (await session.execute(text("SELECT count(*) FROM consents"))).scalar_one() == 0
    with pytest.raises(DBAPIError):  # no UPDATE/DELETE privileges: the ledger is append-only
        async with session_scope(a) as session:
            await session.execute(text("DELETE FROM consents"))


async def test_audit_log_is_append_only_and_private(db: AsyncEngine) -> None:
    a, b = await _make_users(db)
    async with session_scope(a) as session:
        await session.execute(
            text("INSERT INTO audit_events (user_id, actor_id, action) VALUES (:u, :u, 'x')"),
            {"u": a},
        )
    with pytest.raises(DBAPIError):
        async with session_scope(a) as session:
            await session.execute(
                text("INSERT INTO audit_events (user_id, actor_id, action) VALUES (:b, :a, 'x')"),
                {"a": a, "b": b},
            )
    async with session_scope(b) as session:
        assert (await session.execute(text("SELECT count(*) FROM audit_events"))).scalar_one() == 0
    with pytest.raises(DBAPIError):
        async with session_scope(a) as session:
            await session.execute(text("DELETE FROM audit_events"))
    with pytest.raises(DBAPIError):
        async with session_scope(a) as session:
            await session.execute(text("UPDATE audit_events SET action = 'tampered'"))
