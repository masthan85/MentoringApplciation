from collections.abc import Callable

import httpx

Headers = Callable[..., dict[str, str]]


async def test_profile_starts_empty_and_lists_what_is_missing(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    body = (await client.get("/v1/profile", headers=auth())).json()
    assert body["onboarding_status"] == "not_started"
    assert set(body["missing_fields"]) == {
        "role_family",
        "seniority",
        "country",
        "stack",
        "goals_summary",
        "current_challenge",
    }
    assert body["english_variant"] == "en-GB"


async def test_partial_updates_leave_other_fields_alone(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    await client.put(
        "/v1/profile", json={"role_family": "data_engineer", "seniority": "senior"}, headers=h
    )
    body = (
        await client.put("/v1/profile", json={"stack": ["dbt", "Snowflake", "dbt"]}, headers=h)
    ).json()
    assert body["role_family"] == "data_engineer"
    assert body["stack"] == ["dbt", "Snowflake"]  # de-duplicated
    assert body["onboarding_status"] == "in_progress"
    assert "stack" not in body["missing_fields"]


async def test_confirming_needs_a_complete_profile(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    await client.put("/v1/profile", json={"role_family": "ml_ai_engineer"}, headers=h)
    response = await client.put("/v1/profile", json={"confirm_onboarding": True}, headers=h)
    assert response.status_code == 400
    assert "seniority" in response.json()["missing_fields"]
    full = {
        "seniority": "mid",
        "country": "IE",
        "stack": ["python"],
        "goals_summary": "Wants to lead ML projects.",
        "current_challenge": "Models are hard to deploy.",
        "confirm_onboarding": True,
    }
    body = (await client.put("/v1/profile", json=full, headers=h)).json()
    assert body["onboarding_status"] == "complete" and body["missing_fields"] == []


async def test_profile_validation(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    for bad in (
        {"role_family": "wizard"},
        {"seniority": "godlike"},
        {"years_experience": 99},
        {"english_variant": "fr-FR"},
        {"stack": ["x"] * 25},
        {"unknown_field": 1},
        {"writing_mode": "undetectable"},
    ):
        assert (await client.put("/v1/profile", json=bad, headers=h)).status_code in (400, 422), bad


async def test_profiles_are_private(client: httpx.AsyncClient, auth: Headers) -> None:
    await client.put("/v1/profile", json={"job_title": "Staff engineer"}, headers=auth(sub="a"))
    other = (await client.get("/v1/profile", headers=auth(sub="b"))).json()
    assert other["job_title"] is None


async def test_lens_catalogue(client: httpx.AsyncClient, auth: Headers) -> None:
    lenses = (await client.get("/v1/personas", headers=auth())).json()
    assert {lens["id"] for lens in lenses} >= {
        "senior-data-engineer",
        "data-architect",
        "ml-engineer",
    }


async def test_default_persona_follows_the_profile(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    await client.put(
        "/v1/profile", json={"role_family": "data_engineer", "seniority": "lead"}, headers=h
    )
    active = (await client.get("/v1/personas/active", headers=h)).json()
    assert active["lens_ids"] == ["data-architect"] and active["source"] == "default"


async def test_pin_combine_and_return_to_auto(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    pinned = await client.put(
        "/v1/personas/active",
        json={
            "mode": "pinned",
            "lens_ids": ["data-architect", "ai-risk-and-security"],
            "weights": [3, 1],
        },
        headers=h,
    )
    body = pinned.json()
    assert body["source"] == "pinned" and body["weights"] == [0.75, 0.25]
    assert body["names"] == ["Data architect", "AI risk and security reviewer"]
    back = (await client.put("/v1/personas/active", json={"mode": "auto"}, headers=h)).json()
    assert back["source"] == "default" and back["mode"] == "auto"


async def test_persona_validation(client: httpx.AsyncClient, auth: Headers) -> None:
    h = auth()
    for bad in (
        {"mode": "pinned", "lens_ids": []},
        {"mode": "pinned", "lens_ids": ["nope"]},
        {"mode": "pinned", "lens_ids": ["data-architect", "data-architect"]},
        {"mode": "pinned", "lens_ids": ["data-architect", "ml-engineer", "genai-engineer"]},
        {"mode": "pinned", "lens_ids": ["data-architect"], "weights": [1, 2]},
        {"mode": "pinned", "lens_ids": ["data-architect"], "weights": [-1]},
        {"mode": "weird"},
    ):
        assert (await client.put("/v1/personas/active", json=bad, headers=h)).status_code in (
            400,
            422,
        ), bad


async def test_consents_default_to_off_and_are_recorded(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    h = auth()
    assert set((await client.get("/v1/consents", headers=h)).json().values()) == {False}
    on = (
        await client.put("/v1/consents/sensitive_memory", json={"granted": True}, headers=h)
    ).json()
    assert on["sensitive_memory"] is True and on["analytics"] is False
    off = (
        await client.put("/v1/consents/sensitive_memory", json={"granted": False}, headers=h)
    ).json()
    assert off["sensitive_memory"] is False
    assert (
        await client.put("/v1/consents/world_domination", json={"granted": True}, headers=h)
    ).status_code == 404
