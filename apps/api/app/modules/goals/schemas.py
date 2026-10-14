import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
GAS_KEYS = ("-2", "-1", "0", "1", "2")


class GasLevels(BaseModel):
    """The five Goal Attainment Scaling levels, from much worse to much better than expected."""

    model_config = ConfigDict(extra="forbid")

    minus_two: Short
    minus_one: Short
    zero: Short
    plus_one: Short
    plus_two: Short

    def as_dict(self) -> dict[str, str]:
        return {
            "-2": self.minus_two,
            "-1": self.minus_one,
            "0": self.zero,
            "1": self.plus_one,
            "2": self.plus_two,
        }


class GoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Long | None = None
    baseline: Long | None = None
    target_date: date | None = None
    levels: GasLevels
    baseline_score: Annotated[int, Field(ge=-2, le=0)] = -1


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Long | None = None
    target_date: date | None = None
    status: Literal["active", "achieved", "paused", "dropped"] | None = None
    levels: GasLevels | None = None


class ScoreIn(BaseModel):
    score: Annotated[int, Field(ge=-2, le=2)]
    note: Annotated[str, StringConstraints(max_length=1000)] | None = None


class MilestoneIn(BaseModel):
    title: Title
    due_date: date | None = None


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    due_date: date | None
    status: str


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    baseline: str | None
    target_date: date | None
    status: str
    levels: dict[str, str]
    baseline_score: int
    current_score: int
    current_level_text: str
    created_at: datetime
    milestones: list[MilestoneOut] = []


class CommitmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    due_date: date | None = None
    goal_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None


class CommitmentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
        | None
    ) = None
    due_date: date | None = None
    status: Literal["open", "done", "partial", "missed", "dropped"] | None = None
    evidence_url: Annotated[str, StringConstraints(max_length=1000)] | None = None
    evidence_note: Annotated[str, StringConstraints(max_length=2000)] | None = None

    @field_validator("evidence_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Evidence links must start with http:// or https://")
        return value


class CommitmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID | None
    milestone_id: uuid.UUID | None
    title: str
    due_date: date | None
    status: str
    evidence_url: str | None
    evidence_note: str | None
    source: str
    created_at: datetime
    completed_at: datetime | None


class SuggestIn(BaseModel):
    title: Title
    baseline: Long | None = None
    target: Long | None = None


class CommitmentUpdate(BaseModel):
    commitment_id: uuid.UUID
    outcome: Literal["done", "partial", "missed", "dropped"]
    note: Annotated[str, StringConstraints(max_length=1000)] | None = None


class NextCommitment(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    due_date: date | None = None
    goal_id: uuid.UUID | None = None


class CheckInComplete(BaseModel):
    updates: list[CommitmentUpdate] = Field(default_factory=list, max_length=30)
    blockers: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = (
        None
    )
    next_commitment: NextCommitment | None = None


class CheckInOut(BaseModel):
    id: uuid.UUID
    week_start: date
    status: str
    open_commitments: list[CommitmentOut] = []
    reply: str | None = None
    safety_message: str | None = None


class QuarterlyIn(BaseModel):
    gas_scores: dict[uuid.UUID, Annotated[int, Field(ge=-2, le=2)]]
    self_efficacy: list[Annotated[int, Field(ge=1, le=5)]] = Field(min_length=3, max_length=3)
    working_alliance: list[Annotated[int, Field(ge=1, le=5)]] = Field(min_length=3, max_length=3)
    reflection: Annotated[str, StringConstraints(max_length=2000)] | None = None


class BaselineIn(BaseModel):
    self_efficacy: Annotated[int, Field(ge=1, le=5)]


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    period_start: date
    period_end: date
    content: str | None
    scores: dict[str, Any]
    created_at: datetime
