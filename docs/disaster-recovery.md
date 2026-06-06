# Disaster Recovery — Mythos Aegis

## Targets

| Metric | Target |
|---|---|
| **RPO** (Recovery Point Objective) | ≤ 24 hours (daily backup at 02:00 UTC) |
| **RTO** (Recovery Time Objective) | ≤ 2 hours (restore + verify + redeploy) |

Daily backups are written to the `postgres-backup-pvc` PVC by the `postgres-backup` CronJob.  
The last **7** backups are retained; older ones are rotated automatically.

---

## Backup

### Automated (Kubernetes CronJob)

The CronJob `postgres-backup` in namespace `mythos-aegis` runs at 02:00 UTC every day.  
It reads `DATABASE_URL` from the `mythos-aegis-secrets` Secret and writes a compressed dump to `/backups/aegis_<timestamp>.sql.gz`.

```
kubectl -n mythos-aegis get cronjob postgres-backup
kubectl -n mythos-aegis get jobs --selector=app.kubernetes.io/name=postgres-backup
```

### Manual backup

```bash
DATABASE_URL=postgresql://user:pass@host:5432/aegis \
BACKUP_DIR=/backups \
  ./scripts/backup_postgres.sh
```

> **Security**: credentials are parsed from `DATABASE_URL` and exported as libpq environment variables. They are never echoed or written to logs.

---

## Restore

### Prerequisites

- The target database server is reachable.
- `BACKUP_FILE` points to a valid `.sql.gz` backup.
- Caller acknowledges the destructive nature by setting `CONFIRM=yes`.

```bash
BACKUP_FILE=/backups/aegis_20260606T020000Z.sql.gz \
DATABASE_URL=postgresql://user:pass@host:5432/aegis \
CONFIRM=yes \
  ./scripts/restore_postgres.sh
```

The script will:
1. Terminate all active connections to the target database.
2. Drop and recreate the database.
3. Load the compressed dump via `psql`.

### Restore to a specific point in time

If WAL archiving / PITR is configured at the infrastructure level, follow the cloud
provider procedure to restore to a specific LSN before running the application migration.

---

## Verify backup integrity

Run a smoke-test after each manual backup or as part of the weekly runbook:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/aegis \
BACKUP_DIR=/backups \
  ./scripts/verify_restore.sh
```

The script restores the most recent backup into a temporary database named
`aegis_verify_<epoch>`, checks that all 11 SaaS tables exist, then drops
the temporary database unconditionally.

---

## Migration rollback

Each Alembic migration has a `downgrade()` function.

```bash
# Roll back one migration
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade aef8c3b72d1a
```

Current migration chain:

```
aef8c3b72d1a  →  b2f4e8a1c3d5  (SaaS tables)
```

If a migration must be rolled back after data has been written, restore from backup first.

---

## Emergency checklist

- [ ] Confirm data loss window — check the timestamp of the latest backup file.
- [ ] Notify stakeholders — RPO is 24 hours; data since the last backup may be lost.
- [ ] Spin up a restore target — use a staging environment if possible to avoid double-destroy.
- [ ] Run `restore_postgres.sh` with `CONFIRM=yes`.
- [ ] Run `verify_restore.sh` to confirm table integrity.
- [ ] Run `alembic upgrade head` if the restored schema is behind the current revision.
- [ ] Restart application pods: `kubectl -n mythos-aegis rollout restart deployment/aegis-api`.
- [ ] Smoke-test core endpoints: `/health`, `/api/v1/tenants`.
- [ ] Confirm backup CronJob is healthy: `kubectl -n mythos-aegis get cronjob postgres-backup`.

---

## Backup storage security

- `DATABASE_URL` is stored in the `mythos-aegis-secrets` Kubernetes Secret and never hardcoded.
- The backup container runs as a non-root user (`UID 1000`).
- Backup files are gzip-compressed; consider enabling PVC-level encryption at the storage class or cloud-provider level for data at rest.
- Access to the `postgres-backup-pvc` PVC should be restricted to the backup namespace.
