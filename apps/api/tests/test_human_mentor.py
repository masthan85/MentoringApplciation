from collections.abc import Callable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]

LEVELS = {
    "minus_two": "None",
    "minus_one": "Some",
    "zero": "One",
    "plus_one": "Two",
    "plus_two": "Many",
}


def mentee(auth: Headers) -> dict[str, str]:
    return auth(sub="mentee-1", email="mentee@example.com")


def mentor(auth: Headers) -> dict[str, str]:
    return auth(sub="mentor-1", email="Mentor@Example.com")


async def _consent(client: httpx.AsyncClient, h: dict[str, str]) -> None:
    r = await client.put("/v1/consents/mentor_sharing", json={"granted": True}, headers=h)
    assert r.status_code == 200


async def _linked(client: httpx.AsyncClient, auth: Headers) -> dict[str, Any]:
    await _consent(client, mentee(auth))
    invite = (
        await client.post(
            "/v1/mentor-link",
            json={
                "mentor_email": "mentor@example.com",
                "scopes": {"goals": True, "commitments": True},
            },
            headers=mentee(auth),
        )
    ).json()
    accepted = await client.post(
        "/v1/mentor/accept", json={"token": invite["invite_token"]}, headers=mentor(auth)
    )
    assert accepted.status_code == 200, accepted.text
    return {**invite, "link_id": accepted.json()["link_id"]}


async def test_inviting_a_mentor_needs_the_sharing_consent(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    r = await client.post(
        "/v1/mentor-link", json={"mentor_email": "m@example.com"}, headers=mentee(auth)
    )
    assert r.status_code == 403


async def test_only_the_named_mentor_can_accept_and_only_once(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    await _consent(client, mentee(auth))
    invite = (
        await client.post(
            "/v1/mentor-link", json={"mentor_email": "mentor@example.com"}, headers=mentee(auth)
        )
    ).json()
    assert "token_hash" not in invite
    other = auth(sub="other", email="other@example.com")
    assert (
        await client.post(
            "/v1/mentor/accept", json={"token": invite["invite_token"]}, headers=other
        )
    ).status_code == 404
    ok = await client.post(
        "/v1/mentor/accept", json={"token": invite["invite_token"]}, headers=mentor(auth)
    )
    assert ok.status_code == 200
    again = await client.post(
        "/v1/mentor/accept", json={"token": invite["invite_token"]}, headers=mentor(auth)
    )
    assert again.status_code == 404


async def test_a_mentor_sees_nothing_until_the_mentee_approves_a_brief(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    link = await _linked(client, auth)
    await client.post(
        "/v1/goals",
        json={"title": "Lead design reviews", "levels": LEVELS, "baseline_score": -1},
        headers=mentee(auth),
    )
    brief = (
        await client.post(f"/v1/mentor-link/{link['link_id']}/briefs", headers=mentee(auth))
    ).json()
    sections = {s["title"]: s["text"] for s in brief["content"]["sections"]}
    assert "Lead design reviews" in sections["Goals"]

    url = f"/v1/mentor/mentees/{link['link_id']}/brief"
    assert (await client.get(url, headers=mentor(auth))).status_code == 404  # still a draft

    edited = {"sections": [{"title": "Goals", "text": "Only this."}]}
    await client.put(f"/v1/mentor-briefs/{brief['id']}", json=edited, headers=mentee(auth))
    await client.post(f"/v1/mentor-briefs/{brief['id']}/approve", headers=mentee(auth))
    shared = await client.get(url, headers=mentor(auth))
    assert shared.json()["content"]["sections"] == edited["sections"]

    # Editing again withdraws the approval.
    await client.put(f"/v1/mentor-briefs/{brief['id']}", json=edited, headers=mentee(auth))
    assert (await client.get(url, headers=mentor(auth))).status_code == 404

    # The mentee can see who read their brief.
    log = (await client.get("/v1/privacy/access-log", headers=mentee(auth))).json()
    assert any(e["action"] == "mentor.brief_viewed" and e["by"] == "someone else" for e in log)


async def test_a_brief_never_includes_memories_or_conversations(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    link = await _linked(client, auth)
    async with db.begin() as conn:
        uid = (
            await conn.execute(text("SELECT id FROM users WHERE email = 'mentee@example.com'"))
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO memories (user_id, type, content, sensitivity, status) "
                "VALUES (:u, 'goal_context', 'secret health detail', 'normal', 'active')"
            ),
            {"u": uid},
        )
    brief = (
        await client.post(f"/v1/mentor-link/{link['link_id']}/briefs", headers=mentee(auth))
    ).json()
    assert "secret health detail" not in str(brief)


async def test_mentor_notes_reach_the_mentee_and_actions_are_only_proposals(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    link = await _linked(client, auth)
    note = await client.post(
        f"/v1/mentor/mentees/{link['link_id']}/notes",
        json={
            "summary": "We agreed to focus on design reviews.",
            "actions": [{"title": "Draft a design review agenda"}],
        },
        headers=mentor(auth),
    )
    assert note.status_code == 201, note.text
    notes = (await client.get("/v1/session-notes", headers=mentee(auth))).json()
    assert notes[0]["summary"].startswith("We agreed")

    commitments = (await client.get("/v1/commitments", headers=mentee(auth))).json()
    proposed = next(c for c in commitments if c["title"] == "Draft a design review agenda")
    assert (proposed["status"], proposed["source"]) == ("proposed", "human_mentor")
    assert (await client.get("/v1/notifications", headers=mentee(auth))).json()["unread"] >= 1

    accepted = await client.post(f"/v1/commitments/{proposed['id']}/accept", headers=mentee(auth))
    assert accepted.json() == {"status": "open"}
    assert (
        await client.post(f"/v1/commitments/{proposed['id']}/accept", headers=mentee(auth))
    ).status_code == 409


async def test_a_stranger_cannot_add_notes_or_read_briefs(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    link = await _linked(client, auth)
    stranger = auth(sub="stranger", email="s@example.com")
    r = await client.post(
        f"/v1/mentor/mentees/{link['link_id']}/notes", json={"summary": "hi"}, headers=stranger
    )
    assert r.status_code == 404
    assert (
        await client.get(f"/v1/mentor/mentees/{link['link_id']}/brief", headers=stranger)
    ).status_code == 404
    assert (await client.get("/v1/mentor-link", headers=stranger)).json() == []


async def test_ending_a_link_revokes_access_and_removes_shared_briefs(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    link = await _linked(client, auth)
    brief = (
        await client.post(f"/v1/mentor-link/{link['link_id']}/briefs", headers=mentee(auth))
    ).json()
    await client.post(f"/v1/mentor-briefs/{brief['id']}/approve", headers=mentee(auth))
    assert (
        await client.delete(f"/v1/mentor-link/{link['link_id']}", headers=mentee(auth))
    ).status_code == 204
    assert (
        await client.get(f"/v1/mentor/mentees/{link['link_id']}/brief", headers=mentor(auth))
    ).status_code == 404
    r = await client.post(
        f"/v1/mentor/mentees/{link['link_id']}/notes", json={"summary": "x"}, headers=mentor(auth)
    )
    assert r.status_code == 404
    assert (await client.get("/v1/mentor/mentees", headers=mentor(auth))).json() == []
