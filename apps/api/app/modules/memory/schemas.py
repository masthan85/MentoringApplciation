import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    content: str
    confidence: float
    sensitivity: str
    status: str
    source_conversation_id: uuid.UUID | None
    created_at: datetime
    last_confirmed_at: datetime | None


class MemoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
        | None
    ) = None
    type: str | None = Field(default=None)
