from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from app.core.email import set_email_sender
from app.modules.notifications import scheduler
from conftest import FakeLLM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)  # Saturday 3 October; week starts Monday 28 September
LEVELS = {
    "minus_two": "Nothing yet",
    "minus_one": "Some reading",
    "zero": "Led one review",
    "plus_one": "Led two",
    "plus_two": "Ran the forum",
}


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


async def _onboarded(client: httpx.AsyncClient, h: dict[str, str]) -> UUID:
    body = {
        "role_family": "data_engineer",
        "seniority": "senior",
        "stack": ["dbt"],
        "goals_summary": "Grow into architecture.",
        "current_challenge": "No time for design.",
        "confirm_onboarding": True,
    }
    assert (await client.put("/v1/profile", json=body, headers=h)).status_code == 200
    return UUID((await client.get("/v1/me", headers=h)).json()["id"])


async def _goal(client: httpx.AsyncClient, h: dict[str, str]) -> str:
    return (
        await client.post(
            "/v1/goals", json={"title": "Lead design reviews", "levels": LEVELS}, headers=h
        )
    ).json()["id"]


async def _titles(client: httpx.AsyncClient, h: dict[str, str]) -> list[str]:
    return [n["title"] for n in (await client.get("/v1/notifications", headers=h)).json()["items"]]


# ---- notifications API --------------------------------------------------------------------


async def test_notifications_list_read_and_privacy(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h, other = auth(sub="a"), auth(sub="b")
    uid = await _onboarded(client, h)
    await _goal(client, h)
    await scheduler.process_user(uid, NOW)
    listing = (await client.get("/v1/notifications", headers=h)).json()
    assert (
        listing["unread"] == 1
        and listing["items"][0]["title"] == "Your weekly check-in is ready"
        and listing["items"][0]["link"] == "/check-in"
    )
    await client.get("/v1/me", headers=other)
    assert (await client.get("/v1/notifications", headers=other)).json() == {
        "unread": 0,
        "items": [],
    }
    nid = listing["items"][0]["id"]
    assert (await client.post(f"/v1/notifications/{nid}/read", headers=other)).status_code == 404
    assert (await client.post(f"/v1/notifications/{nid}/read", headers=h)).json() == {"marked": 1}
    assert (await client.get("/v1/notifications", headers=h)).json()["unread"] == 0
    assert (await client.post("/v1/notifications/read", headers=h)).json() == {"marked": 0}


# ---- the scheduler --------------------------------------------------------------------------


async def test_the_weekly_check_in_is_announced_once_per_week(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    uid = await _onboarded(client, h)
    assert (await scheduler.process_user(uid, NOW))[
        "notifications"
    ] == 0  # nothing to check in on yet
    await _goal(client, h)
    assert (await scheduler.process_user(uid, NOW))["notifications"] == 1
    assert (await scheduler.process_user(uid, NOW))["notifications"] == 0  # idempotent
    next_week = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
    assert (await scheduler.process_user(uid, next_week))[
        "notifications"
    ] == 1  # a new week, a new check-in


async def test_a_completed_check_in_is_not_announced(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    uid = await _onboarded(client, h)
    await _goal(client, h)
    from app.core.db import session_scope
    from app.modules.goals import checkin
    from app.modules.identity.models import User
    from sqlalchemy import select

    async with session_scope(uid) as session:
        user = (await session.execute(select(User).where(User.id == uid))).scalar_one()
        row = await checkin.current_check_in(session, user, today=checkin.today_london(NOW))
        row.status = "completed"
    assert (await scheduler.process_user(uid, NOW))["notifications"] == 0


async def test_due_and_overdue_commitments_get_one_reminder_each(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    uid = await _onboarded(client, h)
    for title, due in (
        ("Due tomorrow", "2026-10-04"),
        ("Due today", "2026-10-03"),
        ("Way late", "2026-09-01"),
        ("Far away", "2026-12-01"),
    ):
        await client.post("/v1/commitments", json={"title": title, "due_date": due}, headers=h)
    await scheduler.process_user(uid, NOW)
    titles = await _titles(client, h)
    assert (
        "Due tomorrow: Due tomorrow" in titles
        and "Due today: Due today" in titles
        and "Past its date: Way late" in titles
    )
    assert not any("Far away" in t for t in titles)
    before = len(titles)
    await scheduler.process_user(uid, NOW)
    assert len(await _titles(client, h)) == before  # no repeats


async def test_the_monthly_note_is_written_for_last_month_only_when_something_happened(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, db: AsyncEngine
) -> None:
    h = auth()
    uid = await _onboarded(client, h)
    assert (await scheduler.process_user(uid, NOW))["monthly_notes"] == 0  # no activity, no note
    cid = (
        await client.post(
            "/v1/commitments", json={"title": "Run the first design review"}, headers=h
        )
    ).json()["id"]
    await client.patch(f"/v1/commitments/{cid}", json={"status": "done"}, headers=h)
    async with db.begin() as conn:
        await conn.execute(
            text(
                "UPDATE commitments SET completed_at = '2026-09-15T10:00:00Z', created_at = '2026-09-01T10:00:00Z'"
            )
        )
    llm.script.chat_text = "In September you ran your first design review, which was the main thing you set out to do. Next month, line up the second."

    assert (await scheduler.process_user(uid, datetime(2026, 10, 20, 9, 0, tzinfo=UTC)))[
        "monthly_notes"
    ] == 0  # not the first week
    assert (await scheduler.process_user(uid, NOW))["monthly_notes"] == 1
    assert (await scheduler.process_user(uid, NOW))["monthly_notes"] == 0  # once
    notes = (await client.get("/v1/reviews?kind=monthly", headers=h)).json()
    assert (
        len(notes) == 1
        and notes[0]["content"].startswith("In September you ran")
        and notes[0]["period_start"] == "2026-09-01"
    )
    prompt = llm.calls_with("monthly_note")[0].messages[0].content
    assert "Run the first design review" in prompt and "September 2026" in prompt
    assert "Your progress note for September" in await _titles(client, h)


async def test_the_monthly_note_falls_back_to_a_plain_summary(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, db: AsyncEngine
) -> None:
    h = auth()
    uid = await _onboarded(client, h)
    cid = (await client.post("/v1/commitments", json={"title": "Write the ADR"}, headers=h)).json()[
        "id"
    ]
    await client.patch(f"/v1/commitments/{cid}", json={"status": "done"}, headers=h)
    async with db.begin() as conn:
        await conn.execute(
            text(
                "UPDATE commitments SET completed_at = '2026-09-15T10:00:00Z', created_at = '2026-09-01T10:00:00Z'"
            )
        )
    llm.script.chat_text = (
        "When I worked at a startup, I loved this. Great job!"  # an experience claim is rejected
    )
    await scheduler.process_user(uid, NOW)
    note = (await client.get("/v1/reviews?kind=monthly", headers=h)).json()[0]["content"]
    assert note.startswith(
        "In September 2026 you completed 0 weekly check-ins and finished 1 commitments"
    )


async def test_a_quarterly_review_is_announced_once(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth()
    uid = await _onboarded(client, h)
    await _goal(client, h)
    async with db.begin() as conn:
        await conn.execute(text("UPDATE goals SET created_at = '2026-06-01T09:00:00Z'"))
    await scheduler.process_user(uid, NOW)
    assert "Your quarterly review is ready" in await _titles(client, h)
    count = len(await _titles(client, h))
    await scheduler.process_user(uid, NOW)
    assert len(await _titles(client, h)) == count


async def test_emails_go_only_to_users_who_opted_in_and_carry_no_private_detail(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    sender = FakeSender()
    set_email_sender(sender)  # type: ignore[arg-type]
    try:
        h = auth(sub="on", email="on@example.com")
        uid = await _onboarded(client, h)
        await client.post(
            "/v1/commitments",
            json={"title": "Confidential plan to leave my employer", "due_date": "2026-10-03"},
            headers=h,
        )
        await scheduler.process_user(uid, NOW)
        assert sender.sent == []  # not opted in

        assert (await client.put("/v1/profile", json={"email_reminders": True}, headers=h)).json()[
            "email_reminders"
        ] is True
        await client.post(
            "/v1/commitments",
            json={"title": "Another private commitment", "due_date": "2026-10-04"},
            headers=h,
        )
        await scheduler.process_user(uid, NOW)
        assert sender.sent and sender.sent[0][0] == "on@example.com"
        subject, body = sender.sent[0][1], sender.sent[0][2]
        assert "http://localhost:3000" in body and "switch these emails off" in body
        assert "employer" not in body.lower()
        assert subject.startswith(("Your weekly check-in", "Due ", "Past"))
    finally:
        set_email_sender(None)


async def test_the_tick_covers_only_onboarded_users_and_survives_a_failure(
    client: httpx.AsyncClient, auth: Headers, monkeypatch: Any
) -> None:
    ok, broken, not_done = auth(sub="ok"), auth(sub="broken"), auth(sub="newbie")
    ok_id, broken_id = await _onboarded(client, ok), await _onboarded(client, broken)
    await client.get("/v1/me", headers=not_done)
    for h in (ok, broken):
        await _goal(client, h)

    original = scheduler.process_user

    async def flaky(user_id: UUID, now: datetime | None = None) -> dict[str, int]:
        if user_id == broken_id:
            raise RuntimeError("boom")
        return await original(user_id, now)

    monkeypatch.setattr(scheduler, "process_user", flaky)
    totals = await scheduler.run_scheduler(NOW)
    assert totals["users"] == 2 and totals["errors"] == 1 and totals["notifications"] >= 1
    assert "Your weekly check-in is ready" in await _titles(client, ok)
    assert ok_id != broken_id
