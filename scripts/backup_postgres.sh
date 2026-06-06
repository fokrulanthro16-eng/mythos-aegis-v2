#!/usr/bin/env bash
# Dump the Mythos Aegis PostgreSQL database to a timestamped compressed file.
# Retains the most recent 7 backups and rotates older ones.
#
# Required environment variables:
#   DATABASE_URL  — postgresql://user:pass@host:port/dbname
#   BACKUP_DIR    — destination directory (default: /backups)
#
# Credentials are consumed via libpq environment variables only;
# they are never echoed or written to any log.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_LAST=7
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
FILENAME="aegis_${TIMESTAMP}.sql.gz"
DEST="${BACKUP_DIR}/${FILENAME}"

# --- Parse DATABASE_URL into libpq vars without printing any credentials ----
if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[backup] ERROR: DATABASE_URL is not set" >&2
  exit 1
fi

# Extract components using parameter expansion — no subshell that could log them.
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
# Strip any query string
PGDATABASE="${PGDATABASE%%\?*}"

export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE

mkdir -p "${BACKUP_DIR}"

echo "[backup] Starting backup → ${DEST}"
pg_dump \
  --no-password \
  --format=plain \
  --no-privileges \
  --no-owner \
  | gzip -9 > "${DEST}"

echo "[backup] Backup written: ${DEST} ($(du -sh "${DEST}" | cut -f1))"

# --- Rotate: keep only the most recent KEEP_LAST files ----------------------
mapfile -t old_files < <(
  ls -1t "${BACKUP_DIR}"/aegis_*.sql.gz 2>/dev/null | tail -n +"$((KEEP_LAST + 1))"
)

if [[ ${#old_files[@]} -gt 0 ]]; then
  echo "[backup] Rotating ${#old_files[@]} old backup(s)"
  for f in "${old_files[@]}"; do
    rm -f "${f}"
    echo "[backup] Removed ${f}"
  done
fi

echo "[backup] Done. Kept last ${KEEP_LAST} backup(s)."
