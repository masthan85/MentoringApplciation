"""progress: goals, scores, milestones, commitments, check-ins, reviews, notifications, eval runs

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

APP_ROLE = "mentor_app"
UUID = postgresql.UUID(as_uuid=True)
PK = sa.text("gen_random_uuid()")
NOW = sa.func.now()


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


def _own(table: str, privileges: str = "SELECT, INSERT, UPDATE, DELETE") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_own ON {table} "
        f"USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id())"
    )
    _grant(privileges, table)


def _user_fk() -> sa.Column:
    return sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.add_column("profiles", sa.Column("email_reminders", sa.Boolean, nullable=False, server_default=sa.text("false")))

    op.create_table(
        "goals",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("baseline", sa.Text),
        sa.Column("target_date", sa.Date),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("gas_levels", postgresql.JSONB, nullable=False),
        sa.Column("baseline_score", sa.Integer, nullable=False, server_default="-1"),
        sa.Column("current_score", sa.Integer, nullable=False, server_default="-1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("status IN ('active','achieved','paused','dropped')", name="ck_goals_status"),
        sa.CheckConstraint("baseline_score BETWEEN -2 AND 2 AND current_score BETWEEN -2 AND 2", name="ck_goals_scores"),
    )
    op.create_index("ix_goals_user_status", "goals", ["user_id", "status"])
    op.create_table(
        "goal_scores",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.clock_timestamp()),
        sa.CheckConstraint("score BETWEEN -2 AND 2", name="ck_goal_scores_range"),
    )
    op.create_index("ix_goal_scores_goal_time", "goal_scores", ["goal_id", "recorded_at"])
    op.create_table(
        "milestones",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("due_date", sa.Date),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("done_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("status IN ('open','done')", name="ck_milestones_status"),
    )
    op.create_table(
        "commitments",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="SET NULL")),
        sa.Column("milestone_id", UUID, sa.ForeignKey("milestones.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("due_date", sa.Date),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("evidence_url", sa.String(1000)),
        sa.Column("evidence_note", sa.Text),
        sa.Column("source", sa.String(20), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('proposed','open','done','partial','missed','dropped')", name="ck_commitments_status"),
        sa.CheckConstraint("source IN ('user','mentor','human_mentor')", name="ck_commitments_source"),
    )
    op.create_index("ix_commitments_user_status_due", "commitments", ["user_id", "status", "due_date"])
    op.create_table(
        "check_ins",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="due"),
        sa.Column("responses", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reply", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "week_start", name="uq_check_ins_user_week"),
        sa.CheckConstraint("status IN ('due','completed','skipped')", name="ck_check_ins_status"),
    )
    op.create_table(
        "reviews",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("scores", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("user_id", "kind", "period_start", name="uq_reviews_user_kind_period"),
        sa.CheckConstraint("kind IN ('baseline','monthly','quarterly')", name="ck_reviews_kind"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _user_fk(),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("link", sa.String(200)),
        sa.Column("dedupe_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("emailed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_table(
        "eval_runs",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="running"),
        sa.Column("summary", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("results", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("environment", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("mode IN ('smoke','full')", name="ck_eval_runs_mode"),
        sa.CheckConstraint("status IN ('running','finished','failed')", name="ck_eval_runs_status"),
    )

    for table in ("goals", "goal_scores", "milestones", "commitments", "check_ins", "reviews", "notifications"):
        _own(table)
    op.execute("ALTER TABLE eval_runs ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY eval_runs_admin ON eval_runs FOR ALL USING (app_is_admin()) WITH CHECK (app_is_admin())")
    _grant("SELECT, INSERT, UPDATE, DELETE", "eval_runs")

    # The scheduler has to look across users, which row-level security forbids. This returns only
    # ids, and only for people who have finished onboarding.
    op.execute(
        """
        CREATE FUNCTION scheduler_user_ids() RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
          SELECT u.id FROM users u JOIN profiles p ON p.user_id = u.id
          WHERE u.status = 'active' AND p.onboarding_status = 'complete'
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION scheduler_user_ids() FROM PUBLIC")
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT EXECUTE ON FUNCTION scheduler_user_ids() TO {APP_ROLE};
          END IF;
        END $$;
        """
    )


    # The evaluation runner signs in synthetic users. This removes only those, and nobody else.
    op.execute(
        """
        CREATE FUNCTION delete_eval_users() RETURNS integer
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
        DECLARE removed integer;
        BEGIN
          DELETE FROM users WHERE auth_subject LIKE 'eval|%';
          GET DIAGNOSTICS removed = ROW_COUNT;
          RETURN removed;
        END
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION delete_eval_users() FROM PUBLIC")
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT EXECUTE ON FUNCTION delete_eval_users() TO {APP_ROLE};
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS delete_eval_users()")
    op.execute("DROP FUNCTION IF EXISTS scheduler_user_ids()")
    for table in ("eval_runs", "notifications", "reviews", "check_ins", "commitments", "milestones", "goal_scores", "goals"):
        op.drop_table(table)
    op.drop_column("profiles", "email_reminders")
