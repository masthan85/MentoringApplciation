import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    role_family: Mapped[str | None] = mapped_column(String(40))
    seniority: Mapped[str | None] = mapped_column(String(20))
    job_title: Mapped[str | None] = mapped_column(String(120))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    stack: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    goals_summary: Mapped[str | None] = mapped_column(Text)
    current_challenge: Mapped[str | None] = mapped_column(Text)
    english_variant: Mapped[str] = mapped_column(String(5), server_default="en-GB")
    writing_mode: Mapped[str] = mapped_column(String(30), server_default="natural_professional")
    onboarding_status: Mapped[str] = mapped_column(String(20), server_default="not_started")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
