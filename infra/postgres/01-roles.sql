-- Development and CI role setup. Run once as a superuser against the cluster.
--
-- mentor      owner of the schema; runs migrations. Superuser in dev so that
--             CREATE EXTENSION vector works. In production use a managed
--             admin role instead (see docs/adr/0004-database-roles-and-rls.md).
-- mentor_app  runtime role used by the API and worker. Not a superuser and not
--             the table owner, so row-level security applies to it.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mentor') THEN
    CREATE ROLE mentor LOGIN SUPERUSER PASSWORD 'mentor';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mentor_app') THEN
    CREATE ROLE mentor_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'mentor_app';
  END IF;
END
$$;
