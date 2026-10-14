"""Schema for mentor pack files. Validated when the application starts."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.profile.taxonomy import RoleFamily, Seniority


class Lens(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    version: int = Field(ge=1)
    domain: str
    perspective: str
    priorities: list[str] = Field(min_length=3)
    questions_to_ask: list[str] = Field(min_length=3)
    common_failure_modes: list[str] = Field(min_length=2)
    vocabulary: list[str] = Field(default_factory=list)
    terms_to_explain_for_juniors: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    depth_by_seniority: dict[Seniority, str]
    out_of_scope: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _complete(self) -> "Lens":
        missing = set(Seniority) - set(self.depth_by_seniority)
        if missing:
            raise ValueError(f"depth_by_seniority is missing: {sorted(m.value for m in missing)}")
        lowered = self.perspective.lower()
        # Perspectives are viewpoints, never biographies.
        if lowered.startswith(("i ", "i'm", "i am", "you are")) or " i have " in lowered:
            raise ValueError("perspective must be written in the third person")
        return self


class PackMeta(BaseModel):
    id: str
    name: str
    version: int


class Pack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack: PackMeta
    lenses: list[Lens] = Field(min_length=1)


class DefaultRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_family: RoleFamily
    seniority: list[Seniority] | None = None
    lens: str


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_lens: str
    rules: list[DefaultRule]
