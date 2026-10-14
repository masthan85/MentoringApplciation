#!/usr/bin/env bash
# Creates the dev and test databases. Used by docker-compose (initdb) and by
# CI/local setup. Requires psql and a superuser connection via the standard
# PG* environment variables.
set -euo pipefail
for db in mentor mentor_test; do
  if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1; then
    psql -c "CREATE DATABASE ${db} OWNER mentor"
  fi
done
