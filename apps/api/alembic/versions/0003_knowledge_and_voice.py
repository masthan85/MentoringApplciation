"""knowledge and voice: sources, chunks, writing samples, style profiles, drafts, feedback

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

APP_ROLE = "mentor_app"
UUID = postgresql.UUID(as_uuid=True)
PK = sa.text("gen_random_uuid()")
NOW = sa.func.now()
EMBEDDING_DIM = 1536


def _grant(privileges: str, table: str) -> None:
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT {privileges} ON {table} TO {APP_ROLE};
          END IF;
        END $$;
        """
    )


def _own_rows(table: str, privileges: str = "SELECT, INSERT, UPDATE, DELETE") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_own ON {table} "
        f"USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id())"
    )
    _grant(privileges, table)


def upgrade() -> None:
    # Set only by trusted admin code paths (see core.db.set_admin).
    op.execute(
        """
        CREATE FUNCTION app_is_admin() RETURNS boolean
        LANGUAGE sql STABLE AS
        $$ SELECT coalesce(current_setting('app.is_admin', true), '') = 'on' $$
        """
    )
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT EXECUTE ON FUNCTION app_is_admin() TO {APP_ROLE};
          END IF;
        END $$;
        """
    )

    op.create_table(
        "sources",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("publisher", sa.String(200)),
        sa.Column("authority_tier", sa.String(20), nullable=False),
        sa.Column("volatility", sa.String(10), nullable=False, server_default="moderate"),
        sa.Column("domain", sa.String(40), nullable=False),
        sa.Column("subtopic", sa.String(120)),
        sa.Column("jurisdiction", sa.String(10), nullable=False, server_default="global"),
        sa.Column("licence", sa.String(200), nullable=False),
        sa.Column("reviewer", sa.String(200)),
        sa.Column("published_date", sa.Date),
        sa.Column("last_reviewed", sa.Date),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("review_flags", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint(
            "authority_tier IN ('official','standard','peer_reviewed','expert_authored','community')",
            name="ck_sources_tier",
        ),
        sa.CheckConstraint("volatility IN ('stable','moderate','volatile')", name="ck_sources_volatility"),
        sa.CheckConstraint("status IN ('draft','active','retired')", name="ck_sources_status"),
    )
    op.create_table(
        "chunks",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("heading_path", sa.String(500), nullable=False, server_default=""),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("domain", sa.String(40), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR,
            sa.Computed("to_tsvector('english', text)", persisted=True),
        ),
    )
    op.create_index("uq_chunks_source_ordinal", "chunks", ["source_id", "ordinal"], unique=True)
    op.create_index("ix_chunks_domain", "chunks", ["domain"])
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.create_index(
        "ix_chunks_embedding",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # The encyclopedia is shared. Everyone signed in reads active sources; only admin code writes.
    op.execute("ALTER TABLE sources ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY sources_read ON sources FOR SELECT USING (status = 'active' OR app_is_admin())")
    op.execute("CREATE POLICY sources_admin_write ON sources FOR ALL USING (app_is_admin()) WITH CHECK (app_is_admin())")
    op.execute("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chunks_read ON chunks FOR SELECT USING "
        "(app_is_admin() OR EXISTS (SELECT 1 FROM sources s WHERE s.id = source_id AND s.status = 'active'))"
    )
    op.execute("CREATE POLICY chunks_admin_write ON chunks FOR ALL USING (app_is_admin()) WITH CHECK (app_is_admin())")
    _grant("SELECT, INSERT, UPDATE, DELETE", "sources")
    _grant("SELECT, INSERT, UPDATE, DELETE", "chunks")

    op.create_table(
        "writing_samples",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("text_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("word_count", sa.Integer, nullable=False),
        sa.Column("origin", sa.String(20), nullable=False, server_default="user_provided"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("origin IN ('user_provided', 'draft_edit')", name="ck_writing_samples_origin"),
    )
    op.create_index("ix_writing_samples_user_channel", "writing_samples", ["user_id", "channel", "created_at"])
    op.create_table(
        "style_profiles",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("features", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("voice_cards", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("voice_card_override", sa.Text),
        sa.Column("sample_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("user_id", name="uq_style_profiles_user"),
    )
    op.create_table(
        "drafts",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("recipient", sa.String(40), nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("key_points", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("final_text", sa.Text),
        sa.Column("lint", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("similarity", sa.Float),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_index("ix_drafts_user_created", "drafts", ["user_id", "created_at"])
    op.create_table(
        "feedback",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID, sa.ForeignKey("messages.id", ondelete="SET NULL")),
        sa.Column("draft_id", UUID, sa.ForeignKey("drafts.id", ondelete="SET NULL")),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("kind IN ('thumbs_up','thumbs_down','not_like_me','other')", name="ck_feedback_kind"),
    )
    for table in ("writing_samples", "style_profiles", "drafts"):
        _own_rows(table)
    _own_rows("feedback", "SELECT, INSERT, DELETE")


def downgrade() -> None:
    for table in ("feedback", "drafts", "style_profiles", "writing_samples", "chunks", "sources"):
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS app_is_admin()")
