#!/usr/bin/env bash
# Smoke-test a backup by restoring it to a temporary database and checking
# that the expected SaaS tables are present.
#
# Usage:
#   DATABASE_URL=postgresql://user:pass@host:port/dbname \
#   BACKUP_DIR=/backups \
#   ./verify_restore.sh
#
# The script:
#   1. Picks the most recent backup in BACKUP_DIR.
#   2. Restores it into a temp database named "aegis_verify_<timestamp>".
#   3. Checks that core SaaS tables exist.
#   4. Drops the temp database unconditionally (success or failure).
#
# Credentials are consumed via libpq environment variables only;
# they are never echoed or written to any log.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"

# --- Find the most recent backup --------------------------------------------
BACKUP_FILE=$(ls -1t "${BACKUP_DIR}"/aegis_*.sql.gz 2>/dev/null | head -n 1 || true)

if [[ -z "${BACKUP_FILE}" ]]; then
  echo "[verify] ERROR: No backup files found in ${BACKUP_DIR}" >&2
  exit 1
fi

echo "[verify] Using backup: ${BACKUP_FILE}"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[verify] ERROR: DATABASE_URL is not set" >&2
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
# We connect to 'postgres' admin DB for temp db operations
export PGUSER PGPASSWORD PGHOST PGPORT

VERIFY_DB="aegis_verify_$(date -u +%s)"
CLEANUP_DONE=0

cleanup() {
  if [[ "${CLEANUP_DONE}" -eq 0 ]]; then
    CLEANUP_DONE=1
    echo "[verify] Dropping temp database ${VERIFY_DB}…"
    psql --no-password -d postgres \
      -c "DROP DATABASE IF EXISTS \"${VERIFY_DB}\";" > /dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# --- Create temp database and restore ---------------------------------------
psql --no-password -d postgres -c "CREATE DATABASE \"${VERIFY_DB}\";" > /dev/null
echo "[verify] Restoring into ${VERIFY_DB}…"
gunzip -c "${BACKUP_FILE}" | psql --no-password -d "${VERIFY_DB}" > /dev/null

# --- Verify core SaaS tables exist ------------------------------------------
REQUIRED_TABLES=(
  tenants
  tenant_members
  projects
  api_keys
  audit_events
  security_events
  sql_airlock_events
  rate_limit_events
  usage_records
  subscriptions
  system_health_snapshots
)

echo "[verify] Checking tables…"
MISSING=0
for tbl in "${REQUIRED_TABLES[@]}"; do
  count=$(
    psql --no-password -d "${VERIFY_DB}" -tAc \
      "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='${tbl}' AND table_schema='public';"
  )
  if [[ "${count}" -eq 0 ]]; then
    echo "[verify] MISSING table: ${tbl}" >&2
    MISSING=$((MISSING + 1))
  else
    echo "[verify] OK: ${tbl}"
  fi
done

if [[ "${MISSING}" -gt 0 ]]; then
  echo "[verify] FAILED: ${MISSING} table(s) missing from backup." >&2
  exit 1
fi

echo "[verify] All tables present. Backup is valid."
