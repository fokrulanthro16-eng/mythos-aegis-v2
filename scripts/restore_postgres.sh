#!/usr/bin/env bash
# Restore a Mythos Aegis PostgreSQL backup from a compressed dump file.
#
# Usage:
#   BACKUP_FILE=/backups/aegis_20260606T000000Z.sql.gz \
#   DATABASE_URL=postgresql://user:pass@host:port/dbname \
#   ./restore_postgres.sh
#
# The script requires an explicit CONFIRM=yes environment variable to proceed,
# preventing accidental restoration in production.
#
# Credentials are consumed via libpq environment variables only;
# they are never echoed or written to any log.

set -euo pipefail

BACKUP_FILE="${BACKUP_FILE:-}"
CONFIRM="${CONFIRM:-no}"

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "[restore] ERROR: BACKUP_FILE is not set" >&2
  exit 1
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "[restore] ERROR: Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [[ "${CONFIRM}" != "yes" ]]; then
  echo "[restore] ERROR: Set CONFIRM=yes to authorize the restore." >&2
  echo "[restore] This will DROP and recreate the target database." >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[restore] ERROR: DATABASE_URL is not set" >&2
  exit 1
fi

# --- Parse DATABASE_URL into libpq vars without printing any credentials ----
_url="${DATABASE_URL#postgresql://}"
_url="${_url#postgres://}"

PGUSER="${_url%%:*}"
_rest="${_url#*:}"
PGPASSWORD="${_rest%%@*}"
_rest="${_rest#*@}"
PGHOST="${_rest%%:*}"
_rest="${_rest#*:}"
PGPORT="${_rest%%/*}"
PGDATABASE="${_rest#*/}"
PGDATABASE="${PGDATABASE%%\?*}"

export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE

echo "[restore] Restoring ${BACKUP_FILE} → database '${PGDATABASE}' on ${PGHOST}:${PGPORT}"

# Drop all connections and recreate the database.
psql --no-password -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PGDATABASE}' AND pid <> pg_backend_pid();" \
  > /dev/null

psql --no-password -d postgres -c "DROP DATABASE IF EXISTS \"${PGDATABASE}\";" > /dev/null
psql --no-password -d postgres -c "CREATE DATABASE \"${PGDATABASE}\";" > /dev/null

echo "[restore] Database recreated. Loading dump…"
gunzip -c "${BACKUP_FILE}" | psql --no-password -d "${PGDATABASE}" > /dev/null

echo "[restore] Restore complete."
