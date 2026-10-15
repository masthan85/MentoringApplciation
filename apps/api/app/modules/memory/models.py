import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, LargeBinary, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

MEMORY_TYPES = (
    "goal_context",
    "decision",
    "commitment",
    "achievement",
    "preference",
    "improvement_area",
    "project",
    "advice_given",
)


class Memory(Base):
    """A durable fact about the user. Sensitive content is stored encrypted, never in ``content``."""

    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_user_status", "user_id", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    type: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text, server_default="")
    content_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    confidence: Mapped[float] = mapped_column(Float, server_default="0.8")
    sensitivity: Mapped[str] = mapped_column(String(10), server_default="normal")
    # active, or pending (a sensitive item waiting for the user to confirm it)
    status: Mapped[str] = mapped_column(String(10), server_default="active")
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    source_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
