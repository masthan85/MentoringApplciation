"""foundations: users, consents, audit events, row-level security

Revision ID: 0001
Revises:
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "mentor_app"


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


def upgrade() -> None:
    # pgvector is used from phase 2 onwards; install it with the first migration so
    # the database image is validated early.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE FUNCTION app_current_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.current_user_id', true), '')::uuid $$
        """
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("auth_subject", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(320)),
        sa.Column("display_name", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'suspended', 'deleted')", name="ck_users_status"),
    )
    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(60), nullable=False),
        sa.Column("granted", sa.Boolean, nullable=False),
        sa.Column("policy_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_consents_user_purpose", "consents", ["user_id", "purpose", "created_at"])
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100)),
        sa.Column("resource_id", sa.String(100)),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_user_created", "audit_events", ["user_id", "created_at"])

    # Row-level security. The runtime role is neither superuser nor owner, so
    # these policies apply to it.
    for table in ("users", "consents", "audit_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY users_self ON users USING (id = app_current_user_id()) WITH CHECK (id = app_current_user_id())")
    op.execute("CREATE POLICY consents_own ON consents USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id())")
    op.execute("CREATE POLICY audit_select_own ON audit_events FOR SELECT USING (user_id = app_current_user_id())")
    op.execute("CREATE POLICY audit_insert_own ON audit_events FOR INSERT WITH CHECK (user_id IS NOT DISTINCT FROM app_current_user_id())")

    # First sign-in has no user id yet, so provisioning runs as the table owner.
    op.execute(
        """
        CREATE FUNCTION identity_provision_user(p_subject text, p_email text)
        RETURNS TABLE (id uuid, created boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
        DECLARE
          v_id uuid;
        BEGIN
          SELECT u.id INTO v_id FROM users u WHERE u.auth_subject = p_subject;
          IF v_id IS NOT NULL THEN
            RETURN QUERY SELECT v_id, false;
            RETURN;
          END IF;
          INSERT INTO users (auth_subject, email) VALUES (p_subject, p_email)
          ON CONFLICT (auth_subject) DO NOTHING
          RETURNING users.id INTO v_id;
          IF v_id IS NULL THEN
            SELECT u.id INTO v_id FROM users u WHERE u.auth_subject = p_subject;
            RETURN QUERY SELECT v_id, false;
          ELSE
            RETURN QUERY SELECT v_id, true;
          END IF;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION identity_provision_user(text, text) FROM PUBLIC")
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT EXECUTE ON FUNCTION identity_provision_user(text, text) TO {APP_ROLE};
            GRANT EXECUTE ON FUNCTION app_current_user_id() TO {APP_ROLE};
          END IF;
        END $$;
        """
    )

    _grant("SELECT, UPDATE", "users")
    _grant("SELECT, INSERT", "consents")  # append-only ledger
    _grant("SELECT, INSERT", "audit_events")  # append-only


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS identity_provision_user(text, text)")
    op.drop_table("audit_events")
    op.drop_table("consents")
    op.drop_table("users")
    op.execute("DROP FUNCTION IF EXISTS app_current_user_id()")
