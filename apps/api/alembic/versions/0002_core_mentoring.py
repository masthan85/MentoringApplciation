"""core mentoring: profiles, persona configs, conversations, messages, memories

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

APP_ROLE = "mentor_app"
UUID = postgresql.UUID(as_uuid=True)
PK = sa.text("gen_random_uuid()")
NOW = sa.func.now()


def _user_fk() -> sa.Column:
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def _secure(table: str, privileges: str = "SELECT, INSERT, UPDATE, DELETE") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_own ON {table} "
        f"USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id())"
    )
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT {privileges} ON {table} TO {APP_ROLE};
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("role_family", sa.String(40)),
        sa.Column("seniority", sa.String(20)),
        sa.Column("job_title", sa.String(120)),
        sa.Column("years_experience", sa.Integer),
        sa.Column("stack", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("goals_summary", sa.Text),
        sa.Column("current_challenge", sa.Text),
        sa.Column("english_variant", sa.String(5), nullable=False, server_default="en-GB"),
        sa.Column("writing_mode", sa.String(30), nullable=False, server_default="natural_professional"),
        sa.Column("onboarding_status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("user_id", name="uq_profiles_user"),
        sa.CheckConstraint(
            "onboarding_status IN ('not_started', 'in_progress', 'complete')", name="ck_profiles_onboarding"
        ),
    )
    op.create_table(
        "persona_configs",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("mode", sa.String(10), nullable=False, server_default="auto"),
        sa.Column("lens_ids", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("weights", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("user_id", name="uq_persona_configs_user"),
        sa.CheckConstraint("mode IN ('auto', 'pinned')", name="ck_persona_configs_mode"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("kind", sa.String(20), nullable=False, server_default="mentoring"),
        sa.Column("title", sa.String(200)),
        sa.Column("rolling_summary", sa.Text),
        sa.Column("summarised_message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("kind IN ('onboarding', 'mentoring')", name="ck_conversations_kind"),
    )
    op.create_index("ix_conversations_user_updated", "conversations", ["user_id", "updated_at"])
    op.create_table(
        "messages",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("conversation_id", UUID, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        _user_fk(),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])
    op.create_table(
        "memories",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("content_encrypted", sa.LargeBinary),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("sensitivity", sa.String(10), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("source_message_id", UUID, sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("source_conversation_id", UUID, sa.ForeignKey("conversations.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "type IN ('goal_context','decision','commitment','achievement','preference',"
            "'improvement_area','project','advice_given')",
            name="ck_memories_type",
        ),
        sa.CheckConstraint("sensitivity IN ('normal', 'sensitive')", name="ck_memories_sensitivity"),
        sa.CheckConstraint("status IN ('active', 'pending')", name="ck_memories_status"),
        # Sensitive text must never sit in the plain column.
        sa.CheckConstraint(
            "sensitivity = 'normal' OR (content = '' AND content_encrypted IS NOT NULL)",
            name="ck_memories_sensitive_encrypted",
        ),
    )
    op.create_index("ix_memories_user_status", "memories", ["user_id", "status", "created_at"])

    for table in ("profiles", "persona_configs", "conversations", "messages", "memories"):
        _secure(table)


def downgrade() -> None:
    for table in ("memories", "messages", "conversations", "persona_configs", "profiles"):
        op.drop_table(table)
