from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx
import pytest
from app.core.config import Settings
from app.modules.goals import checkin
from app.modules.regions import service as regions
from app.modules.regions.crisis import crisis_message
from app.modules.subscriptions import stripe
from conftest import FakeLLM, parse_sse
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

Headers = Callable[..., dict[str, str]]


def test_every_region_has_a_complete_valid_definition() -> None:
    assert regions.defined() == ["GB", "IE", "US", "CA", "IN"]
    for region in regions._all().values():
        assert regions.valid_timezone(region.timezone)
        assert region.english_variant in regions.ENGLISH_VARIANTS
        assert region.lines and region.emergency and region.career_notes
        assert "global" in region.jurisdictions


@pytest.fixture
def india_on(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "enabled_countries", ["GB", "IE", "US", "CA", "IN"])


def test_india_is_off_by_default_but_defined(settings: Settings) -> None:
    assert regions.codes() == ["GB", "IE", "US", "CA"]
    assert regions.get("IN") is not None


async def test_a_country_that_is_not_enabled_cannot_be_chosen(
    client: httpx.AsyncClient, auth: Headers
) -> None:
    r = await client.put("/v1/profile", json={"country": "IN"}, headers=auth())
    assert r.status_code == 422
    codes = [i["code"] for i in (await client.get("/v1/regions", headers=auth())).json()]
    assert codes == ["GB", "IE", "US", "CA"]


@pytest.mark.parametrize(
    ("country", "must_contain", "must_not_contain"),
    [
        ("GB", ["999", "116 123", "NHS 111"], ["988", "14416"]),
        ("IE", ["112", "116 123", "1800 247 247", "50808"], ["988", "NHS"]),
        ("US", ["911", "988"], ["999", "116 123", "NHS"]),
        ("CA", ["911", "988"], ["999", "116 123", "NHS"]),
        ("IN", ["112", "14416"], ["988", "999", "116 123"]),
    ],
)
def test_each_country_gets_its_own_crisis_resources(
    country: str, must_contain: list[str], must_not_contain: list[str]
) -> None:
    text = crisis_message(country)
    for needle in must_contain:
        assert needle in text, needle
    for needle in must_not_contain:
        assert needle not in text, needle


def test_an_unknown_country_gets_every_supported_line() -> None:
    text = crisis_message(None)
    for needle in ("999", "911", "112", "116 123", "988", "14416"):
        assert needle in text
    assert crisis_message("ZZ") == text


def test_weeks_follow_the_users_time_zone() -> None:
    # 23:30 UTC on Sunday 4 October 2026 is already Monday 5 October in India and Sunday elsewhere.
    moment = datetime(2026, 10, 4, 23, 30, tzinfo=UTC)
    assert checkin.today_in("Asia/Kolkata", moment) == date(2026, 10, 5)
    assert checkin.today_in("America/Toronto", moment) == date(2026, 10, 4)
    assert checkin.today_in("Europe/London", moment) == date(2026, 10, 5)  # BST, one hour ahead
    assert checkin.today_in("Not/AZone", moment) == date(2026, 10, 4)  # falls back to UTC
    assert checkin.today_in(None, moment) == date(2026, 10, 4)
    assert checkin.week_start(date(2026, 10, 4)) == date(2026, 9, 28)


async def test_choosing_a_country_sets_time_zone_and_spelling(
    client: httpx.AsyncClient, auth: Headers, india_on: None
) -> None:
    h = auth()
    body = (await client.put("/v1/profile", json={"country": "US"}, headers=h)).json()
    assert (body["country"], body["timezone"], body["english_variant"]) == (
        "US",
        "America/New_York",
        "en-US",
    )
    # What the user chose themselves is kept.
    body = (
        await client.put(
            "/v1/profile", json={"country": "CA", "timezone": "America/Vancouver"}, headers=h
        )
    ).json()
    assert (body["timezone"], body["english_variant"]) == ("America/Vancouver", "en-CA")
    bad = await client.put("/v1/profile", json={"country": "FR"}, headers=h)
    assert bad.status_code == 422
    assert (
        await client.put("/v1/profile", json={"timezone": "Mars/Base"}, headers=h)
    ).status_code == 422


async def test_the_region_list_is_available(
    client: httpx.AsyncClient, auth: Headers, india_on: None
) -> None:
    items = (await client.get("/v1/regions", headers=auth())).json()
    assert [i["code"] for i in items] == ["GB", "IE", "US", "CA", "IN"]
    assert {i["currency"] for i in items} == {"gbp", "eur", "usd", "cad", "inr"}


async def test_the_mentor_prompt_knows_where_the_user_works(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, india_on: None
) -> None:
    h = auth()
    await client.put("/v1/profile", json={"country": "IN"}, headers=h)
    cid = (await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)).json()[
        "id"
    ]
    r = await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"content": "How do I negotiate my offer?"},
        headers=h,
    )
    assert any(name == "done" for name, _ in parse_sse(r.text))
    system = llm.chat_calls()[-1][1].system or ""
    assert "Where the user works: India" in system and "CTC" in system
    assert "Indian English" in system
    assert "Country: India" in system


async def test_a_crisis_reply_uses_the_users_country(
    client: httpx.AsyncClient, auth: Headers, llm: FakeLLM, india_on: None
) -> None:
    for country, needle in (("US", "988"), ("IN", "14416"), ("IE", "Pieta")):
        h = auth(sub=f"user-{country}", email=f"{country.lower()}@example.com")
        await client.put("/v1/profile", json={"country": country}, headers=h)
        cid = (
            await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)
        ).json()["id"]
        r = await client.post(
            f"/v1/conversations/{cid}/messages",
            json={"content": "I want to end my life"},
            headers=h,
        )
        text = "".join(d["text"] for n, d in parse_sse(r.text) if n == "delta")
        assert needle in text, country
        assert "116 123" not in text or country == "IE"


async def test_retrieval_only_returns_sources_for_the_users_country(
    client: httpx.AsyncClient,
    auth: Headers,
    db: AsyncEngine,
    llm: FakeLLM,
    india_on: None,
) -> None:
    from app.core.db import session_scope
    from app.modules.encyclopedia.ingestion import ingest_document

    def doc(slug: str, jurisdiction: str) -> str:
        return (
            f'---\nslug: {slug}\ntitle: "Notice periods {jurisdiction}"\nauthority_tier: official\n'
            f"domain: career\njurisdiction: {jurisdiction}\nlicence: own\n---\n# Notice\n"
            f"Notice periods and resignation for {jurisdiction} employees are described here.\n"
        )

    async with session_scope(admin=True) as session:
        for code in ("GB", "IN"):
            await ingest_document(session, doc(f"notice-{code.lower()}", code), activate=True)

    llm.script.classify(needs_retrieval=True, domain="career")
    for country, want, other in (
        ("IN", "notice-in", "notice-gb"),
        ("GB", "notice-gb", "notice-in"),
    ):
        h = auth(sub=f"r-{country}", email=f"r{country}@example.com")
        await client.put("/v1/profile", json={"country": country}, headers=h)
        cid = (
            await client.post("/v1/conversations", json={"kind": "mentoring"}, headers=h)
        ).json()["id"]
        r = await client.post(
            f"/v1/conversations/{cid}/messages",
            json={"content": "What notice periods apply when I resign?"},
            headers=h,
        )
        done = next(d for n, d in parse_sse(r.text) if n == "done")
        slugs = {s["slug"] for s in done["sources"]}
        assert want in slugs and other not in slugs, (country, slugs)


async def test_checkout_uses_the_users_currency(
    client: httpx.AsyncClient,
    auth: Headers,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    india_on: None,
) -> None:
    for name, value in {
        "billing_enabled": True,
        "stripe_secret_key": SecretStr("sk_test_x"),
        "stripe_webhook_secret": SecretStr("whsec"),
        "stripe_price_mentor": "price_m",
        "stripe_price_mentor_human": "price_h",
        "stripe_automatic_tax": True,
    }.items():
        monkeypatch.setattr(settings, name, value)
    seen: dict[str, dict[str, str]] = {}

    async def fake_post(path: str, data: dict[str, str]) -> dict[str, str]:
        seen["data"] = data
        return {"url": "https://checkout.example/x"}

    monkeypatch.setattr(stripe, "_post", fake_post)
    h = auth()
    await client.put("/v1/profile", json={"country": "IN"}, headers=h)
    await client.post("/v1/billing/checkout", json={"plan": "mentor"}, headers=h)
    assert seen["data"]["currency"] == "inr"
    assert seen["data"]["automatic_tax[enabled]"] == "true"
