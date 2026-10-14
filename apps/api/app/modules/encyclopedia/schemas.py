import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    url: str | None
    publisher: str | None
    authority_tier: str
    volatility: str
    domain: str
    subtopic: str | None
    jurisdiction: str
    licence: str
    reviewer: str | None
    published_date: date | None
    last_reviewed: date | None
    status: str
    chunk_count: int
    review_flags: list[Any]
    created_at: datetime
    updated_at: datetime


class ChunkOut(BaseModel):
    heading_path: str
    text: str


class SourceDetail(SourceOut):
    chunks: list[ChunkOut]


class SourceCreate(BaseModel):
    """A Markdown document that starts with a front matter block, or HTML with separate metadata."""

    document: str = Field(min_length=20, max_length=400_000)
    kind: Literal["markdown", "html"] = "markdown"
    meta: dict[str, Any] | None = None


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["draft", "active", "retired"] | None = None
    reviewer: str | None = Field(default=None, max_length=200)
    last_reviewed: date | None = None
    authority_tier: (
        Literal["official", "standard", "peer_reviewed", "expert_authored", "community"] | None
    ) = None
    # Required to activate a source whose scan found something that reads like an instruction.
    acknowledge_flags: bool = False


class IngestOut(BaseModel):
    source_id: str
    slug: str
    status: str
    chunks: int
    embedded: int
    unchanged: bool
    findings: list[str]
