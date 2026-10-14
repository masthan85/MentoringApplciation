"""hybrid and launch: human mentor links, briefs, session notes, practice, subscriptions, audit

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
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


def _grant_function(signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(
        f"""
        DO $$ BEGIN
          IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            GRANT EXECUTE ON FUNCTION {signature} TO {APP_ROLE};
          END IF;
        END $$;
        """
    )


def _fk(name: str, table: str) -> sa.Column:
    return sa.Column(name, UUID, sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.drop_constraint("ck_conversations_kind", "conversations")
    op.create_check_constraint(
        "ck_conversations_kind", "conversations", "kind IN ('onboarding','mentoring','practice')"
    )
    op.create_table(
        "mentor_links",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _fk("mentee_id", "users"),
        sa.Column("mentor_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("mentor_email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("scopes", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(10), nullable=False, server_default="invited"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('invited','active','ended')", name="ck_mentor_links_status"),
    )
    op.create_index("ix_mentor_links_mentee", "mentor_links", ["mentee_id", "status"])
    op.create_index("ix_mentor_links_mentor", "mentor_links", ["mentor_user_id", "status"])
    op.create_table(
        "mentor_briefs",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _fk("link_id", "mentor_links"),
        _fk("mentee_id", "users"),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("status IN ('draft','approved')", name="ck_mentor_briefs_status"),
    )
    op.create_index("ix_mentor_briefs_link", "mentor_briefs", ["link_id", "created_at"])
    op.create_table(
        "session_notes",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _fk("link_id", "mentor_links"),
        _fk("mentee_id", "users"),
        _fk("mentor_id", "users"),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_index("ix_session_notes_mentee", "session_notes", ["mentee_id", "created_at"])
    op.create_table(
        "practice_sessions",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        _fk("user_id", "users"),
        sa.Column("conversation_id", UUID, sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_id", sa.String(40), nullable=False),
        sa.Column("context", sa.Text),
        sa.Column("status", sa.String(10), nullable=False, server_default="active"),
        sa.Column("debrief", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active','finished')", name="ck_practice_status"),
    )
    op.create_index("ix_practice_user", "practice_sessions", ["user_id", "created_at"])
    op.create_table(
        "subscriptions",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("stripe_customer_id", sa.String(80)),
        sa.Column("stripe_subscription_id", sa.String(80)),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("plan IN ('free','mentor','mentor_human')", name="ck_subscriptions_plan"),
    )
    op.create_index("ix_subscriptions_customer", "subscriptions", ["stripe_customer_id"])
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )

    # Mentees control their own links, briefs and notes. A mentor can see the links addressed to
    # them; everything else a mentor does goes through the audited functions below.
    for table in ("mentor_links", "mentor_briefs", "session_notes", "practice_sessions", "subscriptions", "stripe_events"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY mentor_links_mentee ON mentor_links "
        "USING (mentee_id = app_current_user_id()) WITH CHECK (mentee_id = app_current_user_id())"
    )
    op.execute("CREATE POLICY mentor_links_mentor ON mentor_links FOR SELECT USING (mentor_user_id = app_current_user_id())")
    op.execute(
        "CREATE POLICY mentor_briefs_mentee ON mentor_briefs "
        "USING (mentee_id = app_current_user_id()) WITH CHECK (mentee_id = app_current_user_id())"
    )
    op.execute("CREATE POLICY session_notes_mentee ON session_notes FOR SELECT USING (mentee_id = app_current_user_id())")
    op.execute("CREATE POLICY session_notes_mentor ON session_notes FOR SELECT USING (mentor_id = app_current_user_id())")
    op.execute(
        "CREATE POLICY practice_own ON practice_sessions "
        "USING (user_id = app_current_user_id()) WITH CHECK (user_id = app_current_user_id())"
    )
    op.execute("CREATE POLICY subscriptions_select ON subscriptions FOR SELECT USING (user_id = app_current_user_id() OR app_is_admin())")
    op.execute("CREATE POLICY subscriptions_admin_write ON subscriptions FOR ALL USING (app_is_admin()) WITH CHECK (app_is_admin())")
    op.execute("CREATE POLICY stripe_events_admin ON stripe_events FOR ALL USING (app_is_admin()) WITH CHECK (app_is_admin())")
    op.execute("CREATE POLICY audit_select_admin ON audit_events FOR SELECT USING (app_is_admin())")
    # Admin-context code (the billing webhook) records events on behalf of a user.
    op.execute("DROP POLICY audit_insert_own ON audit_events")
    op.execute(
        "CREATE POLICY audit_insert_own ON audit_events FOR INSERT "
        "WITH CHECK (user_id IS NOT DISTINCT FROM app_current_user_id() OR app_is_admin())"
    )
    _grant("SELECT, INSERT, UPDATE, DELETE", "mentor_links")
    _grant("SELECT, INSERT, UPDATE, DELETE", "mentor_briefs")
    _grant("SELECT", "session_notes")
    _grant("SELECT, INSERT, UPDATE, DELETE", "practice_sessions")
    _grant("SELECT, INSERT, UPDATE, DELETE", "subscriptions")
    _grant("SELECT, INSERT", "stripe_events")

    # A mentor accepts an invitation with the token the mentee sent them, from the account whose
    # email the mentee named.
    op.execute(
        """
        CREATE FUNCTION mentor_accept_invite(p_token_hash text) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
        DECLARE me uuid := app_current_user_id(); my_email text; link mentor_links%ROWTYPE;
        BEGIN
          IF me IS NULL THEN RAISE EXCEPTION 'not signed in'; END IF;
          SELECT email INTO my_email FROM users WHERE id = me;
          SELECT * INTO link FROM mentor_links WHERE token_hash = p_token_hash FOR UPDATE;
          IF NOT FOUND OR link.status <> 'invited' OR link.expires_at < now()
             OR lower(link.mentor_email) <> lower(coalesce(my_email, '')) OR link.mentee_id = me THEN
            RAISE EXCEPTION 'invitation not valid';
          END IF;
          UPDATE mentor_links SET status = 'active', mentor_user_id = me, accepted_at = now()
            WHERE id = link.id;
          INSERT INTO audit_events (user_id, actor_id, action, resource_type, resource_id)
            VALUES (link.mentee_id, me, 'mentor.link_accepted', 'mentor_link', link.id::text);
          RETURN link.id;
        END
        $$
        """
    )
    # The only way a mentor reads a brief: it must be approved, the link active, and the read is
    # recorded against the mentee.
    op.execute(
        """
        CREATE FUNCTION mentor_view_brief(p_link uuid) RETURNS jsonb
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
        DECLARE me uuid := app_current_user_id(); result jsonb; mentee uuid;
        BEGIN
          SELECT b.content, l.mentee_id INTO result, mentee
          FROM mentor_links l JOIN mentor_briefs b ON b.link_id = l.id
          WHERE l.id = p_link AND l.mentor_user_id = me AND l.status = 'active' AND b.status = 'approved'
          ORDER BY b.approved_at DESC LIMIT 1;
          IF result IS NULL THEN RETURN NULL; END IF;
          INSERT INTO audit_events (user_id, actor_id, action, resource_type, resource_id)
            VALUES (mentee, me, 'mentor.brief_viewed', 'mentor_link', p_link::text);
          RETURN result;
        END
        $$
        """
    )
    # A mentor records a session. Agreed actions arrive as proposals the mentee must accept.
    op.execute(
        """
        CREATE FUNCTION mentor_add_session_note(p_link uuid, p_summary text, p_actions jsonb) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
        DECLARE me uuid := app_current_user_id(); link mentor_links%ROWTYPE; note_id uuid; item jsonb;
        BEGIN
          SELECT * INTO link FROM mentor_links
            WHERE id = p_link AND mentor_user_id = me AND status = 'active';
          IF NOT FOUND THEN RAISE EXCEPTION 'no active link'; END IF;
          INSERT INTO session_notes (link_id, mentee_id, mentor_id, summary)
            VALUES (link.id, link.mentee_id, me, p_summary) RETURNING id INTO note_id;
          FOR item IN SELECT * FROM jsonb_array_elements(coalesce(p_actions, '[]'::jsonb)) LOOP
            INSERT INTO commitments (user_id, title, due_date, status, source)
              VALUES (link.mentee_id, left(item->>'title', 300),
                      nullif(item->>'due_date', '')::date, 'proposed', 'human_mentor');
          END LOOP;
          INSERT INTO notifications (user_id, kind, title, body, link, dedupe_key)
            VALUES (link.mentee_id, 'session_note', 'Your mentor added session notes',
                    'Review the notes and any actions they suggested.', '/mentor-link',
                    'session_note:' || note_id::text);
          INSERT INTO audit_events (user_id, actor_id, action, resource_type, resource_id)
            VALUES (link.mentee_id, me, 'mentor.note_added', 'session_note', note_id::text);
          RETURN note_id;
        END
        $$
        """
    )
    # Deleting an account removes the user and, through cascades, everything they own. The audit
    # trail keeps the event but loses the link to the person.
    op.execute(
        """
        CREATE FUNCTION delete_own_account() RETURNS boolean
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS
        $$
        DECLARE me uuid := app_current_user_id();
        BEGIN
          IF me IS NULL THEN RAISE EXCEPTION 'not signed in'; END IF;
          INSERT INTO audit_events (user_id, actor_id, action, resource_type)
            VALUES (NULL, NULL, 'account.deleted', 'user');
          DELETE FROM users WHERE id = me;
          RETURN FOUND;
        END
        $$
        """
    )
    for signature in (
        "mentor_accept_invite(text)",
        "mentor_view_brief(uuid)",
        "mentor_add_session_note(uuid, text, jsonb)",
        "delete_own_account()",
    ):
        _grant_function(signature)


def downgrade() -> None:
    op.execute("DELETE FROM conversations WHERE kind = 'practice'")
    op.drop_constraint("ck_conversations_kind", "conversations")
    op.create_check_constraint(
        "ck_conversations_kind", "conversations", "kind IN ('onboarding','mentoring')"
    )
    for signature in (
        "delete_own_account()",
        "mentor_add_session_note(uuid, text, jsonb)",
        "mentor_view_brief(uuid)",
        "mentor_accept_invite(text)",
    ):
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
    op.execute("DROP POLICY IF EXISTS audit_select_admin ON audit_events")
    op.execute("DROP POLICY IF EXISTS audit_insert_own ON audit_events")
    op.execute(
        "CREATE POLICY audit_insert_own ON audit_events FOR INSERT "
        "WITH CHECK (user_id IS NOT DISTINCT FROM app_current_user_id())"
    )
    for table in ("stripe_events", "subscriptions", "practice_sessions", "session_notes", "mentor_briefs", "mentor_links"):
        op.drop_table(table)
