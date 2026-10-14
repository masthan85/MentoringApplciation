from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.profile.taxonomy import OnboardingStatus, RoleFamily, Seniority

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
    english_variant: str
    writing_mode: str
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
    english_variant: str | None = None
    writing_mode: str | None = None
    confirm_onboarding: bool = False

    @field_validator("english_variant")
    @classmethod
    def _variant(cls, value: str | None) -> str | None:
        if value is not None and value not in ("en-GB", "en-US"):
            raise ValueError("english_variant must be en-GB or en-US")
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
