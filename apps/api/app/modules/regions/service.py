from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from app.core.config import get_settings

DEFAULT_TIMEZONE = "UTC"
ENGLISH_VARIANTS = {
    "en-GB": "British English",
    "en-US": "American English",
    "en-CA": "Canadian English",
    "en-IN": "Indian English",
}
# Spelling follows British conventions, except American and (mostly) Canadian English.
_AMERICAN_SPELLING = {"en-US"}


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    timezone: str
    english_variant: str
    currency: str
    jurisdictions: tuple[str, ...]
    data_regime: str
    emergency: str
    lines: tuple[str, ...]
    other_help: str
    career_notes: str


@lru_cache
def _all() -> dict[str, Region]:
    raw = yaml.safe_load((Path(__file__).parent / "regions.yaml").read_text())["regions"]
    regions = {}
    for code, item in raw.items():
        crisis = item["crisis"]
        regions[code] = Region(
            code=code,
            name=item["name"],
            timezone=item["timezone"],
            english_variant=item["english_variant"],
            currency=item["currency"],
            jurisdictions=tuple(item["jurisdictions"]),
            data_regime=item["data_regime"],
            emergency=crisis["emergency"],
            lines=tuple(crisis["lines"]),
            other_help=crisis["other"],
            career_notes=" ".join(item["career_notes"].split()),
        )
    return regions


def codes() -> list[str]:
    """Countries a user can choose now."""
    enabled = set(get_settings().enabled_countries)
    return [code for code in _all() if code in enabled]


def defined() -> list[str]:
    return list(_all())


def get(code: str | None) -> Region | None:
    return _all().get(code) if code else None


def country_name(code: str | None) -> str | None:
    region = get(code)
    return region.name if region else None


def currency_for(code: str | None) -> str:
    region = get(code)
    return region.currency if region else "usd"


def listing() -> list[dict[str, str]]:
    enabled = set(codes())
    return [
        {
            "code": r.code,
            "name": r.name,
            "timezone": r.timezone,
            "english_variant": r.english_variant,
            "currency": r.currency,
        }
        for r in _all().values()
        if r.code in enabled
    ]


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def zone(name: str | None) -> ZoneInfo:
    if name and valid_timezone(name):
        return ZoneInfo(name)
    return ZoneInfo(DEFAULT_TIMEZONE)


def spelling_label(variant: str) -> str:
    return ENGLISH_VARIANTS.get(variant, "British English")


def is_american(variant: str) -> bool:
    return variant in _AMERICAN_SPELLING


def retrieval_jurisdictions(code: str | None) -> tuple[str, ...]:
    region = get(code)
    return region.jurisdictions if region else ("global",)


def region_prompt(code: str | None) -> str | None:
    """A short section for the mentor prompt. None when the country is not known."""
    region = get(code)
    if region is None:
        return None
    return (
        f"Where the user works: {region.name}. Spell and phrase in {spelling_label(region.english_variant)}. "
        f"Money is in {region.currency.upper()} unless they say otherwise. "
        "General context about work there (orientation only; do not present it as legal advice, and "
        f"say when something depends on the employer, the province or state, or the contract): {region.career_notes} "
        "If the user says they are working in or moving to another country, follow what they say."
    )
