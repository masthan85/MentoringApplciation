-- Production role setup for Azure Database for PostgreSQL flexible server.
-- Run once as the server administrator (the one created by main.bicep), connected to the
-- `mentor` database. Replace the two passwords, and store them in Key Vault as part of the
-- database-url and migration-database-url secrets.
--
-- mentor      owns the schema and runs migrations. Not a superuser (Azure does not allow it);
--             the `vector` extension is allow-listed by main.bicep, so CREATE EXTENSION works
--             for a member of azure_pg_admin.
-- mentor_app  the role the API and worker connect as. Not the table owner and without
--             BYPASSRLS, so row-level security applies to everything it does.
CREATE ROLE mentor LOGIN PASSWORD 'REPLACE-ME-migration' CREATEROLE;
GRANT azure_pg_admin TO mentor;
CREATE ROLE mentor_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'REPLACE-ME-runtime';
GRANT ALL ON DATABASE mentor TO mentor;
GRANT CONNECT ON DATABASE mentor TO mentor_app;
ALTER DATABASE mentor OWNER TO mentor;
