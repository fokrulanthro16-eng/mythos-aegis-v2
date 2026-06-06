#!/usr/bin/env bash
# Mythos Aegis container entrypoint.
#
# Order of operations:
#   1. Wait until the PostgreSQL port is reachable.
#   2. Run `alembic upgrade head` — fail fast on any migration error.
#   3. Replace this shell with uvicorn (exec ensures signal forwarding).
set -euo pipefail

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"

# ── 1. Wait for PostgreSQL ────────────────────────────────────────────────────
echo "[entrypoint] Waiting for database at ${DB_HOST}:${DB_PORT}..."

python3 - <<'PYCHECK'
import os, socket, sys, time

host = os.environ.get("DB_HOST", "postgres")
port = int(os.environ.get("DB_PORT", "5432"))
deadline = time.monotonic() + 60

while time.monotonic() < deadline:
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print(f"[entrypoint] Database reachable at {host}:{port}")
        sys.exit(0)
    except OSError:
        remaining = int(deadline - time.monotonic())
        print(f"[entrypoint] Waiting for {host}:{port} ({remaining}s left)...")
        time.sleep(2)

print(f"[entrypoint] ERROR: Database at {host}:{port} not reachable after 60 seconds.")
sys.exit(1)
PYCHECK

# ── 2. Run database migrations ────────────────────────────────────────────────
echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

# ── 3. Start the application ─────────────────────────────────────────────────
echo "[entrypoint] Starting Uvicorn on 0.0.0.0:8000..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    --log-level info
