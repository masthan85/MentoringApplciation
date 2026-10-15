import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Scopes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goals: bool = True
    commitments: bool = True


class InviteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mentor_email: EmailStr
    scopes: Scopes = Scopes()


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mentor_email: str
    status: str
    scopes: dict[str, bool]
    created_at: datetime
    accepted_at: datetime | None


class InviteOut(LinkOut):
    # Shown once. Only a hash is stored.
    invite_token: str
    invite_url: str


class AcceptIn(BaseModel):
    token: Annotated[str, StringConstraints(min_length=20, max_length=200)]


class BriefSection(BaseModel):
    title: Annotated[str, StringConstraints(max_length=120)]
    text: Annotated[str, StringConstraints(max_length=3000)]


class BriefContent(BaseModel):
    sections: list[BriefSection] = Field(max_length=12)


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    link_id: uuid.UUID
    status: str
    content: BriefContent
    approved_at: datetime | None
    updated_at: datetime


class SuggestedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]
    due_date: date | None = None


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: Text
    actions: list[SuggestedAction] = Field(default_factory=list, max_length=10)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    link_id: uuid.UUID
    summary: str
    created_at: datetime


class MenteeOut(BaseModel):
    link_id: uuid.UUID
    accepted_at: datetime | None
    scopes: dict[str, bool]
