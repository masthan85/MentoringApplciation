from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.profile.taxonomy import OnboardingStatus, RoleFamily, Seniority
from app.modules.regions.service import ENGLISH_VARIANTS, valid_timezone
from app.modules.regions.service import codes as region_codes

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_family: RoleFamily | None
    seniority: Seniority | None
    job_title: str | None
    years_experience: int | None
    stack: list[str]
    goals_summary: str | None
    current_challenge: str | None
    country: str | None = None
    timezone: str | None = None
    english_variant: str
    writing_mode: str
    email_reminders: bool = False
    onboarding_status: OnboardingStatus
    missing_fields: list[str] = Field(default_factory=list)


class ProfileUpdate(BaseModel):
    """Everything is optional; only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    role_family: RoleFamily | None = None
    seniority: Seniority | None = None
    job_title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = (
        None
    )
    years_experience: Annotated[int, Field(ge=0, le=60)] | None = None
    stack: list[ShortText] | None = Field(default=None, max_length=20)
    goals_summary: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    current_challenge: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    country: str | None = None
    timezone: str | None = None
    english_variant: str | None = None
    writing_mode: str | None = None
    email_reminders: bool | None = None
    confirm_onboarding: bool = False

    @field_validator("english_variant")
    @classmethod
    def _variant(cls, value: str | None) -> str | None:
        if value is not None and value not in ENGLISH_VARIANTS:
            raise ValueError(f"english_variant must be one of {', '.join(ENGLISH_VARIANTS)}")
        return value

    @field_validator("country")
    @classmethod
    def _country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in region_codes():
            raise ValueError(f"country must be one of {', '.join(region_codes())}")
        return value

    @field_validator("timezone")
    @classmethod
    def _timezone(cls, value: str | None) -> str | None:
        if value is not None and not valid_timezone(value):
            raise ValueError("timezone must be an IANA name such as Europe/London")
        return value

    @field_validator("stack")
    @classmethod
    def _stack(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        seen: dict[str, str] = {}
        for item in value:
            if item:
                seen.setdefault(item.lower(), item)
        return list(seen.values())
