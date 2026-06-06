# Mythos Aegis

> **Enterprise Intent Parser and Security Gateway**

Mythos Aegis is a FastAPI-based intent parsing and security boundary gateway with Redis-backed
rate limiting, JWT key rotation, OpenTelemetry tracing, Prometheus metrics, and a multi-stage
CI/CD pipeline.

---

## Quick Start (local, no Docker)

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

---

## Local Verification

The canonical way to run every check before pushing:

**Linux / macOS**
```bash
chmod +x scripts/verify.sh
./scripts/verify.sh
```

**Windows (PowerShell)**
```powershell
.\scripts\verify.ps1
```

Both scripts run, in order:

| Step | Command |
|---|---|
| Format check | `ruff format --check app/` |
| Lint | `ruff check app/` |
| Type check | `mypy app/` |
| Tests + coverage | `pytest --cov=app --cov-fail-under=80` |

**With security checks** (`--security` flag):

```bash
./scripts/verify.sh --security       # Linux/macOS
.\scripts\verify.ps1 -Security       # Windows
```

Security mode adds:

| Step | Tool | What it checks |
|---|---|---|
| Dependency CVE scan | `pip-audit` | OSV database — known CVEs in all installed packages |
| SAST | `bandit -ll` | Medium + high severity Python anti-patterns |
| Secret scan | `detect-secrets` | New secrets introduced beyond the committed baseline |

---

## CI Workflows

Three GitHub Actions workflows run on every pull request and every push to `main`.

### `.github/workflows/ci.yml` — Lint · Type-check · Test

Runs the full quality gate on Python 3.12:

1. `ruff format --check` — formatting
2. `ruff check` — linting (E, F, W, I, UP, B, C4, SIM rules)
3. `mypy` — strict type checking with the pydantic plugin
4. `pytest --cov=app --cov-fail-under=80` — tests + 80% coverage minimum

A coverage XML artifact is uploaded on every run for trend tracking.

### `.github/workflows/docker.yml` — Build · Validate · Smoke-test

1. `docker build` — full image build (catches missing files, broken installs)
2. `docker compose config --quiet` — validates docker-compose syntax and variable references
3. **Non-root assertion** — fails if the container user is `root`
4. **Smoke test** — starts the container (uvicorn only, no migration), polls
   `GET /health/live` for up to 30 seconds, verifies `{"status": "ok"}` response shape

### `.github/workflows/security.yml` — Security · Supply-chain

Runs on PRs, pushes to `main`, and every Monday at 02:00 UTC (catches newly published CVEs):

1. `pip-audit --skip-editable` — queries the OSV database for CVEs in all third-party dependencies; fails on any finding
2. `bandit -r app/ -ll -x app/tests/` — SAST scan; fails on medium or high severity findings; test code is excluded
3. `detect-secrets scan --baseline .secrets.baseline` — compares the current scan against the committed baseline; fails if any new secrets are introduced beyond the baseline

---

## Kubernetes Deployment

### Prerequisites

- Kubernetes ≥ 1.23 (uses `autoscaling/v2`, `policy/v1`, `networking.k8s.io/v1`)
- [Metrics Server](https://github.com/kubernetes-sigs/metrics-server) (for HPA CPU metrics)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx) (or adapt `k8s/ingress.yaml`)
- kubectl configured for your target cluster

### Manifest overview

| File | Kind | Purpose |
|---|---|---|
| [k8s/namespace.yaml](k8s/namespace.yaml) | Namespace | Isolation boundary for all resources |
| [k8s/configmap.yaml](k8s/configmap.yaml) | ConfigMap | Non-sensitive env vars (APP_ENV, OTEL, timeouts) |
| [k8s/secrets.example.yaml](k8s/secrets.example.yaml) | Secret (template) | Schema only — create real secret with `kubectl create secret` |
| [k8s/deployment.yaml](k8s/deployment.yaml) | Deployment | 3 replicas, rolling update, all probes, security hardening |
| [k8s/service.yaml](k8s/service.yaml) | Service | ClusterIP on port 8000 |
| [k8s/ingress.yaml](k8s/ingress.yaml) | Ingress | TLS termination, HTTPS redirect, security headers |
| [k8s/hpa.yaml](k8s/hpa.yaml) | HorizontalPodAutoscaler | CPU 70% target, min 3 / max 10 replicas |
| [k8s/pdb.yaml](k8s/pdb.yaml) | PodDisruptionBudget | minAvailable 2 — protects HA during drains and upgrades |

### Deploy

```bash
# 1. Validate all manifests without applying (dry-run)
kubectl apply --dry-run=client -f k8s/namespace.yaml
kubectl apply --dry-run=client -f k8s/configmap.yaml
kubectl apply --dry-run=client -f k8s/deployment.yaml
kubectl apply --dry-run=client -f k8s/service.yaml
kubectl apply --dry-run=client -f k8s/hpa.yaml
kubectl apply --dry-run=client -f k8s/pdb.yaml

# 2. Create the namespace first (other manifests depend on it)
kubectl apply -f k8s/namespace.yaml

# 3. Create the real secret (replace placeholder values before running)
kubectl create secret generic mythos-aegis-secrets \
  --namespace=mythos-aegis \
  --from-literal=DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/db' \
  --from-literal=JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  --from-literal=JWT_PREVIOUS_SECRET='' \
  --from-literal=REDIS_URL='redis://redis:6379/0'

# 4. Apply remaining manifests
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/pdb.yaml

# 5. Watch rollout
kubectl rollout status deployment/mythos-aegis -n mythos-aegis
```

### Rollout commands

```bash
# Watch rollout progress
kubectl rollout status deployment/mythos-aegis -n mythos-aegis

# View rollout history
kubectl rollout history deployment/mythos-aegis -n mythos-aegis

# Pause a rollout (e.g., to investigate an issue mid-update)
kubectl rollout pause deployment/mythos-aegis -n mythos-aegis

# Resume a paused rollout
kubectl rollout resume deployment/mythos-aegis -n mythos-aegis
```

### Rollback commands

```bash
# Rollback to the previous revision
kubectl rollout undo deployment/mythos-aegis -n mythos-aegis

# Rollback to a specific revision number
kubectl rollout undo deployment/mythos-aegis -n mythos-aegis --to-revision=2

# Confirm rollback completed
kubectl rollout status deployment/mythos-aegis -n mythos-aegis

# Inspect what changed between revisions
kubectl rollout history deployment/mythos-aegis -n mythos-aegis --revision=1
kubectl rollout history deployment/mythos-aegis -n mythos-aegis --revision=2
```

### Scaling commands

```bash
# View current HPA state and recent scaling events
kubectl get hpa mythos-aegis -n mythos-aegis
kubectl describe hpa mythos-aegis -n mythos-aegis

# Manual scale (overrides HPA temporarily — HPA will re-converge)
kubectl scale deployment/mythos-aegis -n mythos-aegis --replicas=5

# Watch pods scale in real time
kubectl get pods -n mythos-aegis -w

# View resource usage per pod (requires Metrics Server)
kubectl top pods -n mythos-aegis
```

### Updating the image

```bash
# Update to a new image tag (triggers rolling update automatically)
kubectl set image deployment/mythos-aegis \
  api=ghcr.io/YOUR_ORG/mythos-aegis:0.2.0 \
  -n mythos-aegis

kubectl rollout status deployment/mythos-aegis -n mythos-aegis
```

### Rotating the JWT secret (zero-downtime)

```bash
# Step 1 — Add new key while keeping the old one as JWT_PREVIOUS_SECRET
kubectl create secret generic mythos-aegis-secrets \
  --namespace=mythos-aegis \
  --from-literal=JWT_SECRET="<new-key>" \
  --from-literal=JWT_PREVIOUS_SECRET="<old-key>" \
  ... \
  --dry-run=client -o yaml | kubectl apply -f -

# Step 2 — Wait until all outstanding tokens issued with the old key expire
# Step 3 — Clear JWT_PREVIOUS_SECRET (old key is retired)
kubectl patch secret mythos-aegis-secrets \
  -n mythos-aegis \
  --type='json' \
  -p='[{"op":"replace","path":"/data/JWT_PREVIOUS_SECRET","value":""}]'
```

---

## Docker — Local Startup

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) ≥ 24
- `docker compose` v2 (bundled with Docker Desktop)

### First run

```bash
cp .env.example .env
docker compose up --build
```

The API is available at `http://localhost:8000`.

### Subsequent runs

```bash
docker compose up
```

### Stop (keeps the postgres volume)

```bash
docker compose down
```

### Full teardown including the database volume

```bash
docker compose down -v
```

### Verify Docker locally

```bash
# 1. Build the image
docker build -t mythos-aegis:local .

# 2. Assert non-root
docker run --rm --entrypoint whoami mythos-aegis:local  # must output: appuser

# 3. Smoke test — no postgres needed
docker run -d --name smoke \
  -e APP_ENV=development \
  -e JWT_SECRET=smoke-test-key-not-for-real-use \
  -p 8000:8000 \
  --entrypoint python \
  mythos-aegis:local \
  -m uvicorn app.main:app --host 0.0.0.0 --port 8000

curl -s http://localhost:8000/health/live   # {"status": "ok"}
docker stop smoke && docker rm smoke
```

---

## Release Readiness Checklist

Before merging to `main` and tagging a release:

- [ ] All three CI workflows pass (CI, Docker, Security)
- [ ] `./scripts/verify.sh --security` passes locally
- [ ] Coverage remains ≥ 80% (`pytest --cov=app --cov-fail-under=80`)
- [ ] No bandit medium/high findings (`bandit -r app/ -ll -x app/tests/`)
- [ ] No dependency CVEs (`pip-audit --skip-editable`)
- [ ] No new unreviewed secrets (`detect-secrets audit .secrets.baseline --list-all-unreviewed`)
- [ ] `.env.example` is up to date with all new environment variables
- [ ] `JWT_SECRET` for the target environment is ≥ 32 characters, not the dev default, stored in a secret manager
- [ ] `APP_ENV=production` verified — app refuses to start with weak/default secrets
- [ ] Non-root container confirmed: `docker run --rm --entrypoint whoami <image>` → `appuser`
- [ ] Alembic migrations applied (`alembic upgrade head` or confirmed via entrypoint log)
- [ ] `/health/ready` returns `{"status": "ready"}` after deployment
- [ ] Kubernetes manifests validate: `kubectl apply --dry-run=client -f k8s/`
- [ ] `kubectl rollout status deployment/mythos-aegis -n mythos-aegis` shows `successfully rolled out`
- [ ] HPA active: `kubectl get hpa -n mythos-aegis` shows current replica count
- [ ] PDB enforced: `kubectl describe pdb -n mythos-aegis` shows `Allowed disruptions: 1`

---

## Database Migrations (Alembic)

Migrations run automatically on container startup via `docker/entrypoint.sh`.

```bash
alembic upgrade head          # apply all pending
alembic current               # show revision
alembic revision --autogenerate -m "describe change"
alembic downgrade -1          # roll back one
alembic history --verbose
```

---

## Environment Variables

Copy `.env.example` to `.env` and customise.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment: `development` \| `staging` \| `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `JWT_SECRET` | *(dev default)* | **Must be ≥ 32 chars and unique in production** |
| `JWT_PREVIOUS_SECRET` | *(empty)* | Previous signing key — set during zero-downtime key rotation |
| `JWT_ISSUER` | `mythos-aegis` | Expected `iss` claim |
| `JWT_AUDIENCE` | `mythos-aegis-api` | Expected `aud` claim |
| `JWT_EXPIRY_SECONDS` | `3600` | Token lifetime in seconds |
| `INTENT_CONFIDENCE_THRESHOLD` | `0.85` | Minimum confidence before any action is dispatched |
| `SQL_TIMEOUT_SECONDS` | `3` | Maximum query wall-clock time |
| `SQL_MAX_LIMIT` | `100` | Maximum analytics result-set rows |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for rate limiting (fail-open if unavailable) |
| `OTEL_ENABLED` | `false` | Set `true` to export traces via OTLP |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318/v1/traces` | OTLP HTTP trace exporter endpoint |
| `OTEL_SERVICE_NAME` | `mythos-aegis` | Service name emitted in trace spans |

---

## Rate Limiting

All requests are rate-limited per-tenant and per-user using Redis-backed fixed windows.
Rate limiting is **fail-open**: if Redis is unavailable, requests are allowed and a warning
is logged.

| Policy | Limit | Scope |
|---|---|---|
| Anonymous (unauthenticated) | 30 req / min | hashed client IP |
| Authenticated (baseline) | 120 req / min | tenant\_id + user\_id |
| SQL Analytics | 60 req / min | tenant\_id + user\_id |
| Write Mutations | 20 req / min | tenant\_id + user\_id |
| Vision (RAG) | 15 req / min | tenant\_id + user\_id |

429 response:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42

{"error": "rate_limit_exceeded"}
```

---

## Secrets Management and Key Rotation

JWT signing keys are managed by `KeyRotationService` in `app/secrets/rotation.py`.

Zero-downtime rotation:

```python
from app.secrets.rotation import get_rotation_service

svc = get_rotation_service()
svc.promote_new_key(new_key)   # old current → previous; new key becomes current
# ... wait until all outstanding tokens expire ...
svc.retire_old_key()            # previous key removed; old tokens no longer valid
```

- `validate_token()` tries current key first, then previous on `InvalidSignatureError`
- Expiry, issuer, and audience failures propagate immediately without retry
- Secret values use `pydantic.SecretStr` — never appear in repr, logs, or tracebacks
- Production refuses to start with missing, default, or short (< 32 chars) secrets

---

## Observability

### Health Endpoints

| Endpoint | Purpose | Probe type |
|---|---|---|
| `GET /health/live` | Process is alive | Kubernetes liveness |
| `GET /health/ready` | Database is reachable | Kubernetes readiness |
| `GET /health/startup` | App has finished initialising | Kubernetes startup |

### Prometheus Metrics

Metrics are served at `GET /metrics`. All names use the `mythos_` prefix.

| Metric | Type | Labels |
|---|---|---|
| `mythos_http_requests_total` | Counter | `method`, `endpoint`, `status_code` |
| `mythos_http_request_duration_seconds` | Histogram | `method`, `endpoint` |
| `mythos_pathway_requests_total` | Counter | `pathway` |
| `mythos_sql_airlock_rejections_total` | Counter | `reason` |
| `mythos_auth_failures_total` | Counter | `failure_type` |
| `mythos_rate_limit_hits_total` | Counter | `policy` |
| `mythos_rate_limit_blocks_total` | Counter | `policy` |
| `mythos_secret_validation_failures_total` | Counter | `reason` |
| `mythos_secret_rotation_total` | Counter | `event` |

High-cardinality fields (`user_id`, `tenant_id`, request bodies) are **never** used as labels.

### OpenTelemetry Tracing

Tracing is opt-in (`OTEL_ENABLED=false` by default). Enable in staging/production:

```bash
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-collector:4318/v1/traces
OTEL_SERVICE_NAME=mythos-aegis
```

JWT tokens, SQL strings, secrets, and Authorization headers are **never** recorded in spans.

---

## Security Boundary

**No action is dispatched until `confidence >= INTENT_CONFIDENCE_THRESHOLD` (default 0.85).**

Inputs below the threshold are routed to `Intent.CLARIFY` with `ActionType.CLARIFICATION`.

Unsafe entity key names (`password`, `token`, `secret`, `api_key`, `credential`, `auth`) are
rejected at schema validation time and never reach downstream handlers.

### Container Security

- API container runs as `appuser` (UID 1001) — never root
- No secrets baked into the Docker image; injected at runtime via environment variables
- `.dockerignore` excludes `.env`, `.env.*`, `.github/`, `scripts/`, and all tool caches

### JWT Authentication

Every `POST /v1/route` request requires a valid Bearer JWT carrying:
`exp`, `iss`, `aud`, `sub` (valid UUID), `tenant_id` (valid UUID), `permissions`.

Tokens are verified by PyJWT before any payload is inspected; the raw token is never logged.

---

## API

### `POST /v1/route` *(requires Bearer JWT)*

```json
{"message": "Cancel my order #1234"}
```

### `POST /intent/parse` *(public)*

```json
{"text": "Cancel my order #1234"}
```

Response:

```json
{
  "intent": "CANCEL_ORDER",
  "confidence": 0.92,
  "entities": {},
  "action_type": "WRITE_MUTATION",
  "raw_text_hash": "<sha256>"
}
```

### Intent Map

| Input keywords | Intent | Action |
|---|---|---|
| cancel / refund / void | `CANCEL_ORDER` | `WRITE_MUTATION` |
| report / sales / revenue | `ANALYTICS_QUERY` | `SQL_ANALYTICS` |
| policy / handbook / SLA | `POLICY_SEARCH` | `RAG_VISION` |
| receipt / invoice / OCR | `VISION_RECEIPT_VALIDATE` | `RAG_VISION` |
| damage / defect / crack | `VISION_DAMAGE_ANALYSIS` | `RAG_VISION` |
| *(low confidence)* | `CLARIFY` | `CLARIFICATION` |
| *(no match)* | `UNKNOWN` | `NOOP` |
