from collections.abc import Callable

import httpx
from app.modules.fingerprint import features as fx
from app.modules.fingerprint.card import describe
from conftest import FakeLLM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]

BRITISH = (
    "I organised the migration last quarter and we didn't hit a single failed load. Honestly, it was less "
    "dramatic than I'd feared. The team analysed the old jobs, prioritised the ones that mattered, and "
    "retired the rest. Why did it go well? We kept the plan small. We checked the counts every morning, "
    "and when something looked odd we asked straight away rather than guessing. I think that habit matters "
    "more than any tool. Next quarter we'll centre the work on lineage, which I'd like to colour in properly "
    "for the finance team so they can see where each figure comes from and trust it. "
    "I've also asked whether we could pair the analysts with the engineers for a week, because the best "
    "ideas usually come from somebody who sees the problem from the other side. We'll try it and see."
)
AMERICAN = (
    BRITISH.replace("organised", "organized")
    .replace("analysed", "analyzed")
    .replace("prioritised", "prioritized")
    .replace("centre", "center")
    .replace("colour", "color")
)
FORMAL = (
    "The programme was delivered in accordance with the agreed schedule. Subsequent verification confirmed "
    "that the reconciliation procedures were completed satisfactorily. Responsibility for ongoing monitoring "
    "has been assigned to the platform engineering function. It is recommended that the steering committee "
    "approve the proposed changes to the operating model at its next scheduled meeting, following the "
    "completion of the outstanding documentation and the formal review of associated risks and dependencies. "
    "Furthermore, it is anticipated that the remaining workstreams will be concluded within the stated "
    "timescales, subject to the availability of the necessary resources and the timely approval of the "
    "relevant change requests by the appropriate governance bodies. Accordingly, the committee is requested "
    "to note the contents of this paper and to confirm its agreement to the recommended course of action."
)


# ---- features --------------------------------------------------------------------------


def test_short_text_gives_no_fingerprint() -> None:
    assert fx.compute_features("Too short to learn anything from.")["insufficient"] is True
    assert describe(fx.compute_features("Too short.")) is None


def test_spelling_variant_and_contractions_are_detected() -> None:
    uk, us = fx.compute_features(BRITISH), fx.compute_features(AMERICAN)
    assert uk["british_ratio"] == 1.0 and us["british_ratio"] == 0.0
    assert (
        uk["contraction_rate"] > 1.0 and uk["first_person_rate"] > 1.0 and uk["question_rate"] > 0
    )
    assert "British English" in (describe(uk) or "") and "American English" in (describe(us) or "")


def test_formal_and_informal_writing_differ() -> None:
    casual, formal = fx.compute_features(BRITISH), fx.compute_features(FORMAL)
    assert formal["formality"] > casual["formality"]
    assert formal["contraction_rate"] < casual["contraction_rate"]
    assert formal["passive_rate"] > casual["passive_rate"]
    assert "formal" in (describe(formal) or "")


def test_vocabulary_diversity_needs_enough_words() -> None:
    assert fx.mtld(["word"] * 10) is None
    varied = fx.mtld(BRITISH.lower().split() * 1)
    repetitive = fx.mtld(("the plan is the plan and the plan is fine " * 12).split())
    assert varied is not None and repetitive is not None and varied > repetitive


def test_similarity_prefers_the_same_style() -> None:
    reference = fx.compute_features(BRITISH)
    same = fx.similarity(fx.compute_features(AMERICAN), reference)
    different = fx.similarity(fx.compute_features(FORMAL), reference)
    assert same is not None and different is not None and same > different
    assert fx.similarity({"insufficient": True}, reference) is None


# ---- samples and the style profile ---------------------------------------------------


async def test_samples_need_ownership_confirmation_and_enough_words(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    body = {"channel": "email", "text": BRITISH, "confirm_own": False}
    assert (await client.post("/v1/writing-samples", json=body, headers=h)).status_code == 400
    assert (
        await client.post(
            "/v1/writing-samples", json={**body, "confirm_own": True, "channel": "fax"}, headers=h
        )
    ).status_code == 400
    assert (
        await client.post(
            "/v1/writing-samples",
            json={**body, "confirm_own": True, "text": "Far too short for this to work"},
            headers=h,
        )
    ).status_code == 400
    ok = await client.post("/v1/writing-samples", json={**body, "confirm_own": True}, headers=h)
    assert (
        ok.status_code == 201
        and ok.json()["word_count"] > 100
        and ok.json()["preview"].startswith("I organised")
    )


async def test_samples_are_encrypted_and_private(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    a, b = auth(sub="a"), auth(sub="b")
    await client.post(
        "/v1/writing-samples",
        json={"channel": "slack", "text": BRITISH, "confirm_own": True},
        headers=a,
    )
    async with db.connect() as conn:
        raw = (await conn.execute(text("SELECT text_encrypted FROM writing_samples"))).scalar_one()
    assert b"organised the migration" not in bytes(raw)
    await client.get("/v1/me", headers=b)
    assert (await client.get("/v1/writing-samples", headers=b)).json() == []
    assert (await client.get("/v1/style-profile", headers=b)).json()["sample_count"] == 0
    sample_id = (await client.get("/v1/writing-samples", headers=a)).json()[0]["id"]
    assert (await client.delete(f"/v1/writing-samples/{sample_id}", headers=b)).status_code == 404


async def test_the_profile_updates_with_samples_and_has_a_readable_voice_card(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    assert (await client.get("/v1/style-profile", headers=h)).json()["voice_cards"] == {}
    await client.post(
        "/v1/writing-samples",
        json={"channel": "email", "text": BRITISH, "confirm_own": True},
        headers=h,
    )
    profile = (await client.get("/v1/style-profile", headers=h)).json()
    assert (
        profile["sample_count"] == 1
        and "email" in profile["features"]
        and "overall" in profile["features"]
    )
    assert "British English" in profile["voice_cards"]["email"]
    sample_id = (await client.get("/v1/writing-samples", headers=h)).json()[0]["id"]
    assert (await client.delete(f"/v1/writing-samples/{sample_id}", headers=h)).status_code == 204
    assert (await client.get("/v1/style-profile", headers=h)).json()["sample_count"] == 0


async def test_the_user_can_replace_the_description_and_delete_everything(
    client: httpx.AsyncClient, auth: Headers, db: AsyncEngine
) -> None:
    h = auth()
    await client.post(
        "/v1/writing-samples",
        json={"channel": "email", "text": BRITISH, "confirm_own": True},
        headers=h,
    )
    mine = "Short and direct. No pleasantries. Dry humour."
    assert (
        await client.put("/v1/style-profile/voice-card", json={"voice_card": mine}, headers=h)
    ).json()["voice_card_override"] == mine
    deleted = await client.delete("/v1/style-profile", headers=h)
    assert deleted.json() == {"deleted_samples": 1}
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM writing_samples"))).scalar_one() == 0
        assert (await conn.execute(text("SELECT count(*) FROM style_profiles"))).scalar_one() == 0


async def test_the_fingerprint_shapes_the_chat_prompt_and_the_lint_baseline(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    await client.post(
        "/v1/writing-samples",
        json={"channel": "chat", "text": BRITISH, "confirm_own": True},
        headers=h,
    )
    await client.put(
        "/v1/profile", json={"writing_mode": "my_style", "english_variant": "en-GB"}, headers=h
    )
    cid = (await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)).json()[
        "id"
    ]
    await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"content": "How should I plan next quarter's lineage work?"},
        headers=h,
    )
    system = llm.chat_calls()[-1][1].system or ""
    assert "Match the user's own writing style" in system
    assert (
        "Spells in British English" in system
        and "<writing_example>" in system
        and "organised the migration" in system
    )


# ---- chat voice: modes and lint feedback ------------------------------------------------


async def test_the_writing_mode_changes_the_prompt_and_lint_is_recorded(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, db: AsyncEngine
) -> None:
    h = auth()
    await client.put(
        "/v1/profile", json={"writing_mode": "concise", "english_variant": "en-US"}, headers=h
    )
    cid = (await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)).json()[
        "id"
    ]
    llm.script.chat_text = "Great question! Furthermore, it is important to note that this is a robust and seamless approach. I hope this helps!"
    await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"content": "What should I check before a release?"},
        headers=h,
    )
    system = llm.chat_calls()[-1][1].system or ""
    assert "As short as the content allows" in system and "American English" in system
    async with db.connect() as conn:
        meta = (
            await conn.execute(text("SELECT meta FROM messages WHERE role='assistant'"))
        ).scalar_one()
    assert meta["voice"] == {"mode": "concise", "fingerprint": False}
    assert "formulaic_opener" in meta["lint"]["failed"] and meta["lint"]["passed"] is False

    llm.script.chat_text = "Check the counts."
    await client.post(
        f"/v1/conversations/{cid}/messages", json={"content": "And after the release?"}, headers=h
    )
    assert "flagged for: a generic opener" in (
        llm.chat_calls()[-1][1].system or ""
    )  # learns from its last reply


async def test_onboarding_is_not_linted(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, db: AsyncEngine
) -> None:
    h = auth()
    cid = (await client.post("/v1/conversations", json={"kind": "onboarding"}, headers=h)).json()[
        "id"
    ]
    await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"content": "Hello there, I work with data"},
        headers=h,
    )
    async with db.connect() as conn:
        assert (
            await conn.execute(text("SELECT meta->'lint' FROM messages WHERE role='assistant'"))
        ).scalar_one() is None


# ---- Studio ---------------------------------------------------------------------------


REQUEST = {
    "channel": "exec_summary",
    "recipient": "cto",
    "purpose": "Ask for approval to move the nightly load to Snowflake",
    "key_points": "Cost falls from 4200 to 3150 pounds a month. Cutover on 12 March 2026. Risk: two weeks of parallel running.",
}
CLEAN = (
    "I recommend we move the nightly load to Snowflake. I need your approval by Friday. Monthly cost falls "
    "from 4200 to 3150 pounds, and cutover is on 12 March 2026, after two weeks of parallel running. That "
    "parallel running is the main risk. If we do nothing, we keep paying the higher bill and the old jobs "
    "stay fragile."
)


async def test_a_clean_draft_is_returned_as_written(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    llm.script.chat_text = CLEAN
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=auth())).json()
    assert draft["text"] == CLEAN and draft["adjusted"] is False and draft["lint"]["passed"] is True
    assert draft["warnings"] == [] and draft["id"]
    system = llm.calls_with("studio_draft")[0].system or ""
    assert "Executive summary" in system and "Use only the facts" in system


async def test_a_mechanical_draft_is_tidied_without_changing_facts(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    llm.script.chat_text = (
        "Great question! I recommend we move the nightly load to Snowflake. Monthly cost falls from 4200 to 3150 pounds. "
        "Cutover is on 12 March 2026, after two weeks of parallel running. I hope this helps!"
    )
    # Spans, in order, are the opener and the closer: remove both.
    llm.script.rewrites = [{"index": 0, "text": ""}, {"index": 1, "text": ""}]
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=auth())).json()
    assert (
        draft["adjusted"] is True
        and "Great question" not in draft["text"]
        and "hope this helps" not in draft["text"]
    )
    assert "3150" in draft["text"] and "12 March 2026" in draft["text"]
    assert len(draft["lint_after_adjustment"]["failed"]) < len(draft["lint"]["failed"])


async def test_a_rewrite_that_changes_a_fact_is_thrown_away(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    original = (
        "Great question! I recommend we move the nightly load to Snowflake. Monthly cost falls from 4200 to 3150 pounds. "
        "Cutover is on 12 March 2026, after two weeks of parallel running. I hope this helps!"
    )
    llm.script.chat_text = original
    llm.script.rewrites = [
        {"index": 0, "text": "I recommend we move to Snowflake, saving 5000 pounds."},
        {"index": 1, "text": ""},
    ]
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=auth())).json()
    assert (
        draft["adjusted"] is False
        and draft["text"] == original
        and "preservation check failed" in draft["adjustment_note"]
    )


async def test_invented_numbers_in_a_draft_raise_a_warning(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    llm.script.chat_text = CLEAN + " This will also cut incidents by 40% according to our analysis."
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=auth())).json()
    assert any("numbers you did not provide" in w and "40%" in w for w in draft["warnings"])


async def test_studio_refuses_prohibited_and_crisis_requests_without_calling_a_model(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    fake = await client.post(
        "/v1/studio/drafts",
        json={**REQUEST, "purpose": "Write a forged certificate for my CV", "channel": "email"},
        headers=h,
    )
    assert fake.json()["refused"] == "prohibited" and "can't help" in fake.json()["message"]
    crisis = await client.post(
        "/v1/studio/drafts",
        json={**REQUEST, "key_points": "I want to end my life, tell my manager"},
        headers=h,
    )
    assert crisis.json()["refused"] == "crisis" and "116 123" in crisis.json()["message"]
    assert llm.provider.calls == []


async def test_studio_validation_and_privacy(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth(sub="a")
    assert (
        await client.post("/v1/studio/drafts", json={**REQUEST, "channel": "fax"}, headers=h)
    ).status_code == 422
    assert (
        await client.post("/v1/studio/drafts", json={**REQUEST, "purpose": "x"}, headers=h)
    ).status_code == 422
    llm.script.chat_text = CLEAN
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=h)).json()
    other = auth(sub="b")
    assert (await client.get(f"/v1/studio/drafts/{draft['id']}", headers=other)).status_code == 404
    assert (
        await client.post(
            f"/v1/studio/drafts/{draft['id']}/edit",
            json={"final_text": "Edited text here."},
            headers=other,
        )
    ).status_code == 404
    assert [d["id"] for d in (await client.get("/v1/studio/drafts", headers=h)).json()] == [
        draft["id"]
    ]


async def test_edits_teach_the_fingerprint_only_with_consent(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    llm.script.chat_text = CLEAN
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=h)).json()
    edited = BRITISH
    off = (
        await client.post(
            f"/v1/studio/drafts/{draft['id']}/edit", json={"final_text": edited}, headers=h
        )
    ).json()
    assert off == {
        "saved": True,
        "learned": False,
        "reason": "Learning from your edits is switched off.",
    }
    assert (await client.get("/v1/writing-samples", headers=h)).json() == []

    await client.put("/v1/consents/fingerprint_learning", json={"granted": True}, headers=h)
    on = (
        await client.post(
            f"/v1/studio/drafts/{draft['id']}/edit", json={"final_text": edited}, headers=h
        )
    ).json()
    assert on["learned"] is True
    samples = (await client.get("/v1/writing-samples", headers=h)).json()
    assert samples[0]["origin"] == "draft_edit" and samples[0]["channel"] == "exec_summary"
    assert (await client.get(f"/v1/studio/drafts/{draft['id']}", headers=h)).json()[
        "text"
    ] == edited


async def test_similarity_to_the_users_own_style_is_reported(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM
) -> None:
    h = auth()
    await client.post(
        "/v1/writing-samples",
        json={"channel": "exec_summary", "text": BRITISH, "confirm_own": True},
        headers=h,
    )
    llm.script.chat_text = CLEAN
    draft = (await client.post("/v1/studio/drafts", json=REQUEST, headers=h)).json()
    assert draft["similarity"] is not None and 0 <= draft["similarity"] <= 1


# ---- feedback --------------------------------------------------------------------------


async def test_feedback_on_messages_and_drafts(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, db: AsyncEngine
) -> None:
    h, other = auth(sub="a"), auth(sub="b")
    cid = (await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)).json()[
        "id"
    ]
    await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"content": "Tell me something useful about reruns"},
        headers=h,
    )
    message_id = (await client.get(f"/v1/conversations/{cid}", headers=h)).json()["messages"][1][
        "id"
    ]
    ok = await client.post(
        "/v1/feedback",
        json={"kind": "not_like_me", "message_id": message_id, "note": "Too formal"},
        headers=h,
    )
    assert ok.status_code == 201
    await client.get("/v1/me", headers=other)
    assert (
        await client.post(
            "/v1/feedback", json={"kind": "thumbs_up", "message_id": message_id}, headers=other
        )
    ).status_code == 404
    assert (
        await client.post("/v1/feedback", json={"kind": "thumbs_up"}, headers=h)
    ).status_code == 400
    assert (
        await client.post(
            "/v1/feedback", json={"kind": "angry", "message_id": message_id}, headers=h
        )
    ).status_code == 422
    async with db.connect() as conn:
        assert (await conn.execute(text("SELECT kind, note FROM feedback"))).one() == (
            "not_like_me",
            "Too formal",
        )
