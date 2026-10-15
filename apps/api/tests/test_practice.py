from collections.abc import Callable

import httpx
from conftest import FakeLLM, parse_sse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]


async def _start(
    client: httpx.AsyncClient, h: dict[str, str], scenario: str = "salary_conversation"
) -> dict:  # type: ignore[type-arg]
    r = await client.post(
        "/v1/practice",
        json={
            "scenario_id": scenario,
            "context": "I want to ask for a 10% rise after leading the migration.",
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_scenarios_are_listed(client: httpx.AsyncClient, auth: Headers) -> None:
    items = (await client.get("/v1/practice/scenarios", headers=auth())).json()
    assert {s["id"] for s in items} == {
        "mock_interview",
        "salary_conversation",
        "difficult_one_to_one",
        "architecture_review",
    }


async def test_a_rehearsal_plays_a_role_and_ends_with_a_debrief(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, db: AsyncEngine
) -> None:
    h = auth()
    practice = await _start(client, h)
    for line in (
        "Thanks for making time. I have led the migration.",
        "It saved us 30% on compute.",
    ):
        r = await client.post(
            f"/v1/conversations/{practice['conversation_id']}/messages",
            json={"content": line},
            headers=h,
        )
        assert any(name == "done" for name, _ in parse_sse(r.text))

    system = llm.chat_calls()[-1][1].system or ""
    assert "rehearsal" in system and "line manager" in system
    assert "ask for a 10% rise" in system
    assert "<situation>" in system

    done = (await client.post(f"/v1/practice/{practice['id']}/finish", headers=h)).json()
    assert done["status"] == "finished"
    assert done["debrief"]["improvements"] == ["State the ask earlier."]

    # A rehearsal is not what the user thinks, so nothing from it becomes a memory.
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM memories"))).scalar_one() == 0


async def test_a_debrief_with_too_little_to_review_says_so(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    practice = await _start(client, h, "mock_interview")
    done = (await client.post(f"/v1/practice/{practice['id']}/finish", headers=h)).json()
    assert "not enough" in done["debrief"]["summary"]


async def test_live_interview_help_is_still_refused_inside_a_rehearsal(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    practice = await _start(client, h, "mock_interview")
    r = await client.post(
        f"/v1/conversations/{practice['conversation_id']}/messages",
        json={
            "content": "I'm in my actual interview right now, tell me what to say without them noticing"
        },
        headers=h,
    )
    done = next(data for name, data in parse_sse(r.text) if name == "done")
    assert done.get("fixed_reply") == "refusal"


async def test_a_setup_that_asks_for_something_prohibited_is_rejected(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    r = await client.post(
        "/v1/practice",
        json={
            "scenario_id": "mock_interview",
            "context": "During my real interview I want you to tell me what to say without them noticing",
        },
        headers=auth(),
    )
    assert r.status_code == 409


async def test_practice_is_private_to_its_owner(client: httpx.AsyncClient, auth: Headers) -> None:
    practice = await _start(client, auth(sub="a", email="a@example.com"))
    other = auth(sub="b", email="b@example.com")
    assert (
        await client.post(f"/v1/practice/{practice['id']}/finish", headers=other)
    ).status_code == 404
    assert (await client.get("/v1/practice", headers=other)).json() == []
