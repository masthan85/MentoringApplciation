import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

Channel = Literal["slack", "email", "exec_summary", "adr", "linkedin", "interview_spoken"]
Recipient = Literal[
    "cto",
    "executive",
    "peer",
    "team",
    "manager",
    "recruiter",
    "hiring_manager",
    "stakeholder",
    "other",
]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class DraftRequest(BaseModel):
    channel: Channel
    recipient: Recipient = "other"
    purpose: Annotated[Text, StringConstraints(min_length=5, max_length=1000)]
    key_points: Annotated[Text, StringConstraints(min_length=5, max_length=4000)]
    mode: str | None = Field(default=None, description="Overrides the writing mode in the profile")


class DraftOut(BaseModel):
    id: uuid.UUID | None = None
    refused: str | None = None
    message: str | None = None
    channel: str | None = None
    recipient: str | None = None
    text: str | None = None
    adjusted: bool = False
    adjustment_note: str | None = None
    lint: dict[str, Any] | None = None
    lint_after_adjustment: dict[str, Any] | None = None
    similarity: float | None = None
    warnings: list[str] = []
    created_at: datetime | None = None


class EditIn(BaseModel):
    final_text: Annotated[Text, StringConstraints(min_length=5, max_length=20000)]


class EditOut(BaseModel):
    saved: bool
    learned: bool
    reason: str | None = None
