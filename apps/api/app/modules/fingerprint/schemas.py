import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints


class SampleIn(BaseModel):
    channel: str
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=30000)]
    confirm_own: bool = Field(description="The user confirms they wrote this text themselves.")


class SampleOut(BaseModel):
    id: uuid.UUID
    channel: str
    origin: str
    word_count: int
    preview: str
    created_at: datetime


class StyleProfileOut(BaseModel):
    sample_count: int
    features: dict[str, Any]
    voice_cards: dict[str, str]
    voice_card_override: str | None


class VoiceCardIn(BaseModel):
    voice_card: Annotated[str, StringConstraints(max_length=1500)] | None = None
