import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

GOAL_STATUSES = ("active", "achieved", "paused", "dropped")
COMMITMENT_STATUSES = ("proposed", "open", "done", "partial", "missed", "dropped")
GAS_LEVELS = ("-2", "-1", "0", "1", "2")


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _user() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))


class Goal(Base):
    """A goal with Goal Attainment Scaling levels from -2 (much less than expected) to +2 (much more)."""

    __tablename__ = "goals"
    __table_args__ = (Index("ix_goals_user_status", "user_id", "status"),)

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = _user()
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    baseline: Mapped[str | None] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), server_default="active")
    gas_levels: Mapped[dict[str, Any]] = mapped_column(JSONB)
    baseline_score: Mapped[int] = mapped_column(Integer, server_default="-1")
    current_score: Mapped[int] = mapped_column(Integer, server_default="-1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GoalScore(Base):
    """Every recorded GAS score, so progress can be shown as a trend."""

    __tablename__ = "goal_scores"
    __table_args__ = (Index("ix_goal_scores_goal_time", "goal_id", "recorded_at"),)

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = _user()
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE")
    )
    score: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))  # baseline, review, manual
    note: Mapped[str | None] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = _user()
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), server_default="open")
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Commitment(Base):
    __tablename__ = "commitments"
    __table_args__ = (Index("ix_commitments_user_status_due", "user_id", "status", "due_date"),)

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = _user()
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL")
    )
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("milestones.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), server_default="open")
    evidence_url: Mapped[str | None] = mapped_column(String(1000))
    evidence_note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(
        String(20), server_default="user"
    )  # user, mentor, human_mentor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CheckIn(Base):
    __tablename__ = "check_ins"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_check_ins_user_week"),)

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = _user()
    week_start: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), server_default="due")  # due, completed, skipped
    responses: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    reply: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base):
    """A monthly progress note or a quarterly review."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "period_start", name="uq_reviews_user_kind_period"),
    )

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = _user()
    kind: Mapped[str] = mapped_column(String(10))  # baseline, monthly, quarterly
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    content: Mapped[str | None] = mapped_column(Text)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
