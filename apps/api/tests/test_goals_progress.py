from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import httpx
from conftest import FakeLLM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]

LEVELS = {
    "minus_two": "No design work done",
    "minus_one": "Read about design reviews",
    "zero": "Led one design review",
    "plus_one": "Led two design reviews",
    "plus_two": "Ran the architecture forum",
}
GOAL = {
    "title": "Lead design reviews",
    "baseline": "Never led one",
    "levels": LEVELS,
    "baseline_score": -1,
}


async def _goal(client: httpx.AsyncClient, h: dict[str, str], **overrides: Any) -> dict[str, Any]:
    response = await client.post("/v1/goals", json={**GOAL, **overrides}, headers=h)
    assert response.status_code == 201, response.text
    return response.json()


# ---- goals ----------------------------------------------------------------------------


async def test_a_goal_carries_gas_levels_and_a_baseline_score(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    goal = await _goal(client, auth(), target_date=str(date.today() + timedelta(days=90)))
    assert goal["levels"] == {
        "-2": "No design work done",
        "-1": "Read about design reviews",
        "0": "Led one design review",
        "1": "Led two design reviews",
        "2": "Ran the architecture forum",
    }
    assert (goal["baseline_score"], goal["current_score"]) == (-1, -1)
    assert goal["current_level_text"] == "Read about design reviews"


async def test_goal_validation(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    bad_cases = [
        {**GOAL, "levels": {k: v for k, v in LEVELS.items() if k != "zero"}},
        {**GOAL, "levels": {**LEVELS, "zero": ""}},
        {**GOAL, "baseline_score": 1},
        {**GOAL, "title": "x"},
        {**GOAL, "surprise": True},
    ]
    for body in bad_cases:
        assert (await client.post("/v1/goals", json=body, headers=h)).status_code == 422, body


async def test_focus_is_enforced_with_a_limit_on_active_goals(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    ids = [(await _goal(client, h, title=f"Goal number {i}"))["id"] for i in range(5)]
    sixth = await client.post("/v1/goals", json={**GOAL, "title": "One too many"}, headers=h)
    assert sixth.status_code == 400 and "up to 5" in sixth.json()["detail"]
    await client.patch(f"/v1/goals/{ids[0]}", json={"status": "paused"}, headers=h)
    assert (
        await client.post("/v1/goals", json={**GOAL, "title": "Now there is room"}, headers=h)
    ).status_code == 201
    assert (
        await client.patch(f"/v1/goals/{ids[0]}", json={"status": "active"}, headers=h)
    ).status_code == 400


async def test_scores_move_the_current_level_and_keep_history(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth()
    goal = await _goal(client, h)
    moved = (
        await client.post(
            f"/v1/goals/{goal['id']}/scores",
            json={"score": 1, "note": "Led two reviews"},
            headers=h,
        )
    ).json()
    assert moved["current_score"] == 1 and moved["current_level_text"] == "Led two design reviews"
    assert (
        await client.post(f"/v1/goals/{goal['id']}/scores", json={"score": 3}, headers=h)
    ).status_code == 422
    async with db.connect() as conn:
        rows = (
            await conn.execute(text("SELECT source, score FROM goal_scores ORDER BY recorded_at"))
        ).all()
    assert [tuple(r) for r in rows] == [("baseline", -1), ("manual", 1)]


async def test_milestones_and_deleting_a_goal(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    goal = await _goal(client, h)
    milestone = (
        await client.post(
            f"/v1/goals/{goal['id']}/milestones",
            json={"title": "Shadow a review", "due_date": "2027-01-15"},
            headers=h,
        )
    ).json()
    done = (await client.post(f"/v1/milestones/{milestone['id']}/done", headers=h)).json()
    assert done["status"] == "done"
    listed = (await client.get("/v1/goals", headers=h)).json()
    assert listed[0]["milestones"][0]["title"] == "Shadow a review"
    assert (await client.delete(f"/v1/goals/{goal['id']}", headers=h)).status_code == 204
    assert (await client.get("/v1/goals", headers=h)).json() == []


async def test_goals_are_private(client: httpx.AsyncClient, auth: Headers) -> None:
    a, b = auth(sub="a"), auth(sub="b")
    goal = await _goal(client, a)
    await client.get("/v1/me", headers=b)
    assert (await client.get("/v1/goals", headers=b)).json() == []
    assert (
        await client.patch(f"/v1/goals/{goal['id']}", json={"title": "Hijacked goal"}, headers=b)
    ).status_code == 404
    assert (
        await client.post(
            f"/v1/goals/{goal['id']}/milestones", json={"title": "Sneaky one"}, headers=b
        )
    ).status_code == 404
    assert (
        await client.post(
            "/v1/commitments",
            json={"title": "Linked to a stranger", "goal_id": goal["id"]},
            headers=b,
        )
    ).status_code == 404


async def test_levels_can_be_suggested_and_the_user_stays_in_control(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    suggested = await client.post(
        "/v1/goals/suggest-levels",
        json={
            "title": "Lead design reviews",
            "baseline": "Never led one",
            "target": "Lead one a quarter",
        },
        headers=auth(),
    )
    assert suggested.status_code == 200 and suggested.json()["zero"] == "Led one design review"
    prompt = llm.calls_with("gas_suggestion")[0]
    assert "Never led one" in prompt.messages[0].content and "Goal Attainment Scaling" in (
        prompt.system or ""
    )
    llm.script.gas = {"nonsense": "yes"}
    assert (
        await client.post(
            "/v1/goals/suggest-levels", json={"title": "Another goal here"}, headers=auth()
        )
    ).status_code == 400


# ---- commitments ------------------------------------------------------------------------


async def test_commitments_lifecycle(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    goal = await _goal(client, h)
    created = (
        await client.post(
            "/v1/commitments",
            json={
                "title": "Book a design review slot",
                "due_date": "2026-11-01",
                "goal_id": goal["id"],
            },
            headers=h,
        )
    ).json()
    assert created["status"] == "open" and created["source"] == "user"
    done = (
        await client.patch(
            f"/v1/commitments/{created['id']}",
            json={
                "status": "done",
                "evidence_url": "https://example.com/doc",
                "evidence_note": "Invite sent",
            },
            headers=h,
        )
    ).json()
    assert (
        done["status"] == "done"
        and done["completed_at"]
        and done["evidence_url"] == "https://example.com/doc"
    )
    reopened = (
        await client.patch(f"/v1/commitments/{created['id']}", json={"status": "open"}, headers=h)
    ).json()
    assert reopened["completed_at"] is None
    assert (
        await client.patch(
            f"/v1/commitments/{created['id']}",
            json={"evidence_url": "javascript:alert(1)"},
            headers=h,
        )
    ).status_code == 422
    assert [
        c["id"] for c in (await client.get("/v1/commitments?status=open", headers=h)).json()
    ] == [created["id"]]
    assert (await client.delete(f"/v1/commitments/{created['id']}", headers=h)).status_code == 204


async def test_open_commitments_are_capped(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    for i in range(12):
        assert (
            await client.post(
                "/v1/commitments", json={"title": f"Small step number {i}"}, headers=h
            )
        ).status_code == 201
    over = await client.post("/v1/commitments", json={"title": "The thirteenth step"}, headers=h)
    assert over.status_code == 400 and "12 open" in over.json()["detail"]


# ---- weekly check-in ----------------------------------------------------------------------


async def _two_commitments(client: httpx.AsyncClient, h: dict[str, str]) -> tuple[str, str]:
    a = (
        await client.post(
            "/v1/commitments",
            json={"title": "Draft the review agenda", "due_date": "2026-10-10"},
            headers=h,
        )
    ).json()["id"]
    b = (
        await client.post(
            "/v1/commitments",
            json={"title": "Ask Sam for feedback", "due_date": "2026-10-12"},
            headers=h,
        )
    ).json()["id"]
    return a, b


async def test_the_check_in_is_one_per_week_and_lists_open_commitments(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    a, b = await _two_commitments(client, h)
    first = (await client.get("/v1/check-ins/current", headers=h)).json()
    again = (await client.get("/v1/check-ins/current", headers=h)).json()
    assert first["id"] == again["id"] and first["status"] == "due"
    assert {c["id"] for c in first["open_commitments"]} == {a, b}


async def test_completing_a_check_in_updates_commitments_and_replies_from_the_facts(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    a, b = await _two_commitments(client, h)
    check_in = (await client.get("/v1/check-ins/current", headers=h)).json()
    llm.script.chat_text = (
        "You got the agenda done, which was the harder one. Ask Sam by Friday, then."
    )
    result = (
        await client.post(
            f"/v1/check-ins/{check_in['id']}/complete",
            json={
                "updates": [
                    {"commitment_id": a, "outcome": "done"},
                    {"commitment_id": b, "outcome": "missed", "note": "Sam was away"},
                ],
                "blockers": "Hard to find time with the release",
                "next_commitment": {"title": "Message Sam for feedback", "due_date": "2026-10-23"},
            },
            headers=h,
        )
    ).json()
    assert result["status"] == "completed" and result["reply"].startswith("You got the agenda done")
    prompt = llm.calls_with("checkin_reply")[0].messages[0].content
    assert "Done: Draft the review agenda" in prompt and "Not done: Ask Sam for feedback" in prompt
    assert (
        "Hard to find time with the release" in prompt
        and "Message Sam for feedback by 2026-10-23" in prompt
    )

    commitments = {
        c["title"]: c["status"] for c in (await client.get("/v1/commitments", headers=h)).json()
    }
    assert commitments == {
        "Draft the review agenda": "done",
        "Ask Sam for feedback": "missed",
        "Message Sam for feedback": "open",
    }
    assert (
        await client.post(f"/v1/check-ins/{check_in['id']}/complete", json={}, headers=h)
    ).status_code == 400  # only once


async def test_a_check_in_cannot_touch_closed_or_foreign_commitments(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h, other = auth(sub="a"), auth(sub="b")
    a, _ = await _two_commitments(client, h)
    theirs = (
        await client.post("/v1/commitments", json={"title": "Somebody else's task"}, headers=other)
    ).json()["id"]
    check_in = (await client.get("/v1/check-ins/current", headers=h)).json()
    assert (
        await client.post(
            f"/v1/check-ins/{check_in['id']}/complete",
            json={"updates": [{"commitment_id": theirs, "outcome": "done"}]},
            headers=h,
        )
    ).status_code == 404
    await client.patch(f"/v1/commitments/{a}", json={"status": "done"}, headers=h)
    closed = await client.post(
        f"/v1/check-ins/{check_in['id']}/complete",
        json={"updates": [{"commitment_id": a, "outcome": "done"}]},
        headers=h,
    )
    assert closed.status_code == 400 and "not an open commitment" in closed.json()["detail"]
    assert (await client.get("/v1/check-ins/current", headers=other)).json()["id"] != check_in["id"]


async def test_crisis_language_in_a_check_in_gets_the_fixed_message_and_no_model(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    check_in = (await client.get("/v1/check-ins/current", headers=h)).json()
    result = (
        await client.post(
            f"/v1/check-ins/{check_in['id']}/complete",
            json={"blockers": "I can't go on, I want to end my life"},
            headers=h,
        )
    ).json()
    assert "116 123" in result["safety_message"] and result["reply"] is None
    assert llm.calls_with("checkin_reply") == []


async def test_the_reply_falls_back_if_the_model_fails_or_overclaims(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    a, _ = await _two_commitments(client, h)
    llm.script.chat_text = "When I worked at a bank I did the same. Well done."
    check_in = (await client.get("/v1/check-ins/current", headers=h)).json()
    result = (
        await client.post(
            f"/v1/check-ins/{check_in['id']}/complete",
            json={"updates": [{"commitment_id": a, "outcome": "done"}]},
            headers=h,
        )
    ).json()
    assert result["reply"].startswith("Thanks for checking in. You finished 1 of 1")


async def test_a_check_in_can_be_skipped(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    check_in = (await client.get("/v1/check-ins/current", headers=h)).json()
    assert (await client.post(f"/v1/check-ins/{check_in['id']}/skip", headers=h)).json()[
        "status"
    ] == "skipped"


# ---- reviews -------------------------------------------------------------------------------


async def test_baseline_and_quarterly_review_with_trends(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth()
    goal = await _goal(client, h)
    assert (await client.post("/v1/baseline", json={"self_efficacy": 2}, headers=h)).json() == {
        "self_efficacy": 2.0
    }
    status = (await client.get("/v1/reviews/quarterly/status", headers=h)).json()
    assert (
        status["due"] is False
        and len(status["self_efficacy_items"]) == 3
        and len(status["working_alliance_items"]) == 3
    )

    async with db.begin() as conn:  # time passes: the goal was set 100 days ago
        await conn.execute(text("UPDATE goals SET created_at = now() - interval '100 days'"))
    assert (await client.get("/v1/reviews/quarterly/status", headers=h)).json()["due"] is True

    incomplete = await client.post(
        "/v1/reviews/quarterly",
        json={"gas_scores": {}, "self_efficacy": [3, 3, 4], "working_alliance": [4, 4, 5]},
        headers=h,
    )
    assert incomplete.status_code == 400 and goal["id"] in incomplete.json()["missing_goal_ids"]
    body = {
        "gas_scores": {goal["id"]: 0},
        "self_efficacy": [3, 4, 4],
        "working_alliance": [4, 4, 5],
        "reflection": "Led my first review",
    }
    review = (await client.post("/v1/reviews/quarterly", json=body, headers=h)).json()
    assert (
        review["kind"] == "quarterly"
        and review["scores"]["self_efficacy"] == 3.67
        and review["scores"]["working_alliance"] == 4.33
    )

    assert (
        await client.post("/v1/reviews/quarterly", json=body, headers=h)
    ).status_code == 400  # not twice in a day
    assert (await client.get("/v1/reviews/quarterly/status", headers=h)).json()["due"] is False
    assert (await client.get("/v1/goals", headers=h)).json()[0]["current_score"] == 0

    trends = (await client.get("/v1/reviews/trends", headers=h)).json()
    assert [p["score"] for p in trends["goals"][0]["points"]] == [-1, 0]
    assert [p["kind"] for p in trends["self_efficacy"]] == ["baseline", "quarterly"] and trends[
        "working_alliance"
    ][0]["value"] == 4.33
    assert len((await client.get("/v1/reviews", headers=h)).json()) == 2


async def test_review_scores_must_be_valid_and_for_active_goals(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    goal = await _goal(client, h)
    base = {"self_efficacy": [3, 3, 3], "working_alliance": [3, 3, 3]}
    assert (
        await client.post(
            "/v1/reviews/quarterly", json={**base, "gas_scores": {goal["id"]: 5}}, headers=h
        )
    ).status_code == 422
    assert (
        await client.post(
            "/v1/reviews/quarterly",
            json={**base, "self_efficacy": [3, 3], "gas_scores": {goal["id"]: 0}},
            headers=h,
        )
    ).status_code == 422
    stranger = "00000000-0000-4000-8000-000000000000"
    assert (
        await client.post(
            "/v1/reviews/quarterly",
            json={**base, "gas_scores": {goal["id"]: 0, stranger: 0}},
            headers=h,
        )
    ).status_code == 400


# ---- Today ---------------------------------------------------------------------------------


async def test_today_chooses_the_right_nudge(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    empty = (await client.get("/v1/today", headers=h)).json()
    assert (
        empty["nudge"]["kind"] == "commit"
        and empty["next_commitment"] is None
        and empty["goals"] == []
    )

    goal = await _goal(client, h)
    due = (await client.get("/v1/today", headers=h)).json()
    assert (
        due["check_in_due"] is True
        and due["nudge"]["kind"] == "check_in"
        and due["goals"][0]["id"] == goal["id"]
    )

    check_in = (await client.get("/v1/check-ins/current", headers=h)).json()
    await client.post(f"/v1/check-ins/{check_in['id']}/complete", json={}, headers=h)
    overdue_id = (
        await client.post(
            "/v1/commitments",
            json={"title": "Old task still open", "due_date": "2020-01-01"},
            headers=h,
        )
    ).json()["id"]
    late = (await client.get("/v1/today", headers=h)).json()
    assert (
        late["nudge"]["kind"] == "overdue"
        and late["next_commitment"]["overdue"] is True
        and late["next_commitment"]["id"] == overdue_id
    )

    await client.patch(f"/v1/commitments/{overdue_id}", json={"status": "done"}, headers=h)
    await client.post(
        "/v1/commitments",
        json={"title": "Plan the next review", "due_date": "2999-01-01"},
        headers=h,
    )
    steady = (await client.get("/v1/today", headers=h)).json()
    assert (
        steady["nudge"]["kind"] == "next"
        and "Plan the next review by 2999-01-01" in steady["nudge"]["text"]
    )


# ---- the mentor knows about goals and commitments -------------------------------------------


async def test_goals_and_commitments_reach_the_mentoring_prompt(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    await _goal(client, h)
    await client.post(
        "/v1/commitments",
        json={"title": "Present the lineage proposal", "due_date": "2020-02-02"},
        headers=h,
    )
    cid = (await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)).json()[
        "id"
    ]
    await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"content": "What should I focus on this week?"},
        headers=h,
    )
    system = llm.chat_calls()[-1][1].system or ""
    assert "<goals>" in system and "Goal: Lead design reviews (now scored -1" in system
    assert "Commitment: Present the lineage proposal, overdue 2020-02-02" in system
    assert (
        "never nag" in system and system.index("<user_profile>") < system.index("<goals>")
        if "<user_profile>" in system
        else True
    )
