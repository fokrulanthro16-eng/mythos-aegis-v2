# Mythos Aegis

> **Multi-tenant AI SaaS Platform**

Mythos Aegis is a production-grade AI SaaS backend with a premium admin console.
It ships RAG (document Q&A), Vision analysis, an agentic runtime, workflow orchestration,
metered billing, and a hardened security layer — all multi-tenant, all behind JWT RBAC.

---

## What's included

| Layer | What it does |
|---|---|
| **RAG Pipeline** | Upload docs → chunk → embed (Ollama) → semantic search → grounded Q&A with citations |
| **Vision Intelligence** | Analyze JPEG/PNG/WebP/GIF with a vision LLM; optional RAG indexing |
| **Agent Runtime** | Tool-calling agent loop backed by Ollama; structured tool-call records returned |
| **Workflow Engine** | Multi-step workflow execution with retry, timeout, and step-level observability |
| **Billing** | Mock (local) or Stripe: plans, checkout, subscription, quota enforcement |
| **Intent Parser** | Deterministic keyword router → action dispatch → SQL Airlock |
| **SQL Airlock** | Multi-stage SQL validation: fingerprint, intent, injection check |
| **Admin Console** | Next.js 15 dark console at `localhost:3001` — tenants, RAG, Vision, Agent, Billing |
| **JWT Auth** | HS256 Bearer tokens; zero-downtime key rotation; tenant isolation |
| **Rate Limiting** | Redis-backed per-tenant windows; fail-open when Redis unavailable |
| **Observability** | Prometheus metrics, OpenTelemetry tracing, structured JSON logs |

---

## Quick Start (local, no Docker)

### 1 — Backend

```bash
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env

# Apply DB migrations (requires a running Postgres)
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

### 2 — Admin console

```bash
cd apps/admin
npm install
npm run dev          # → http://localhost:3001
```

### 3 — Generate a demo JWT

From the repo root (dev secret is pre-configured in `.env`):

```powershell
# Windows PowerShell
.venv\Scripts\python.exe -c @"
import jwt, time
payload = {
    'sub': '11111111-1111-1111-1111-111111111111',
    'tenant_id': '11111111-1111-1111-1111-111111111111',
    'iss': 'mythos-aegis',
    'aud': 'mythos-aegis-api',
    'iat': int(time.time()),
    'exp': int(time.time()) + 86400,
    'roles': ['admin'],
    'permissions': [
        'rag.upload','rag.search','rag.ask',
        'vision.analyze','vision.extract',
        'agent.run','agent.sessions.read','agent.sessions.write',
        'billing.read','billing.manage'
    ],
}
print(jwt.encode(payload, 'mythos-aegis-dev-secret-change-in-production', algorithm='HS256'))
"@
```

```bash
# Linux/macOS
python -c "
import jwt, time
payload = {
    'sub': '11111111-1111-1111-1111-111111111111',
    'tenant_id': '11111111-1111-1111-1111-111111111111',
    'iss': 'mythos-aegis',
    'aud': 'mythos-aegis-api',
    'iat': int(time.time()),
    'exp': int(time.time()) + 86400,
    'roles': ['admin'],
    'permissions': [
        'rag.upload','rag.search','rag.ask',
        'vision.analyze','vision.extract',
        'agent.run','agent.sessions.read','agent.sessions.write',
        'billing.read','billing.manage'
    ],
}
print(jwt.encode(payload, 'mythos-aegis-dev-secret-change-in-production', algorithm='HS256'))
"
```

Paste the printed token into the **amber config bar** at the top of every admin console page.

### 4 — Demo values

| Field | Value |
|---|---|
| JWT Token | *(output of step 3 above — expires in 24 h, regenerate as needed)* |
| Project ID | `22222222-2222-2222-2222-222222222222` |

The project ID is a free-form UUID used to namespace RAG documents and agent sessions.
No database row is required — the services use it as a filter key.

---

## Prerequisites

| Dependency | Purpose | Required for |
|---|---|---|
| Python 3.12+ | Backend | Always |
| PostgreSQL 15+ | Primary database | Always |
| Node.js 20+ | Admin console | Admin UI |
| Ollama | Local LLM inference | RAG, Vision, Agent |
| Redis | Rate limiting | Optional (fail-open) |

### Ollama models

```bash
ollama pull qwen2.5:1.5b        # RAG ask + Agent
ollama pull nomic-embed-text    # RAG embedding
ollama pull qwen2.5-vl:7b       # Vision (7B; use llama3.2-vision:11b as fallback)
```

---

## Local Verification

```bash
# Linux/macOS
./scripts/verify.sh              # lint + type-check + tests + coverage
./scripts/verify.sh --security   # above + pip-audit + bandit + detect-secrets

# Windows
.\scripts\verify.ps1
.\scripts\verify.ps1 -Security
```

| Step | Command |
|---|---|
| Format | `ruff format --check app/` |
| Lint | `ruff check app/` |
| Type check | `mypy app/` |
| Tests + coverage ≥80% | `pytest --cov=app --cov-fail-under=80` |

---

## CI Workflows

### `ci.yml` — Lint · Type-check · Test

1. `ruff format --check` + `ruff check`
2. `mypy` strict
3. `pytest --cov=app --cov-fail-under=80`

### `docker.yml` — Build · Smoke-test

1. `docker build` — full image
2. Non-root assertion (`whoami` → `appuser`)
3. Smoke: starts container, polls `GET /health/live` for 30 s

### `security.yml` — CVE · SAST · Secret scan

Runs on PRs, pushes to `main`, and weekly:

1. `pip-audit` — OSV CVE database
2. `bandit -ll` — medium/high severity Python anti-patterns
3. `detect-secrets` — new secrets vs. committed baseline

---

## API Overview

All routes at `/v1/` require `Authorization: Bearer <jwt>`.

### RAG

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/rag/upload` | Upload doc (FormData: `file` + `project_id`) |
| `POST` | `/v1/rag/ask` | Q&A (`{ project_id, question }`) |
| `GET` | `/v1/rag/documents` | List docs (`?project_id=<uuid>`) |
| `POST` | `/v1/rag/search` | Semantic search |

### Vision

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/vision/analyze` | Analyze image (FormData: `file` + `project_id` + optional `prompt`) |
| `POST` | `/v1/vision/extract` | Extract PDF text |

### Agent

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/agent/run` | Run agent (`{ project_id, question }`) |
| `GET` | `/v1/agent/sessions` | List sessions |
| `GET` | `/v1/agent/sessions/{id}` | Get session |

### Billing

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/billing/plans` | Public — list plans |
| `GET` | `/v1/billing/subscription` | Current subscription |
| `GET` | `/v1/billing/quota` | Quota + feature flags |
| `GET` | `/v1/billing/invoices` | Invoice list |
| `POST` | `/v1/billing/checkout` | Create checkout session |
| `POST` | `/v1/billing/checkout/activate` | Activate (mock/Stripe webhook) |
| `DELETE` | `/v1/billing/subscription` | Cancel subscription |

### Core

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/intent/parse` | Public | Parse intent |
| `POST` | `/v1/route` | JWT | Route through security gateway |
| `GET` | `/health/live` | Public | Liveness |
| `GET` | `/health/ready` | Public | Readiness (DB ping) |
| `GET` | `/metrics` | Public | Prometheus metrics |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in values.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` \| `staging` \| `production` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/mythos_aegis` | Async PostgreSQL |
| `JWT_SECRET` | *(dev default)* | **≥32 chars in production** |
| `JWT_ISSUER` | `mythos-aegis` | Expected `iss` claim |
| `JWT_AUDIENCE` | `mythos-aegis-api` | Expected `aud` claim |
| `JWT_EXPIRY_SECONDS` | `3600` | Token lifetime |
| `REDIS_URL` | `redis://localhost:6379/0` | Rate limiting (fail-open) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama inference server |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Text generation model |
| `RAG_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model (Ollama) |
| `RAG_EMBEDDING_DIMENSION` | `768` | Must match model output |
| `RAG_CHUNK_SIZE` | `800` | Chars per document chunk |
| `RAG_TOP_K` | `5` | Chunks retrieved per query |
| `VISION_MODEL` | `qwen2.5-vl:7b` | Vision LLM (Ollama) |
| `AGENT_MODEL` | `qwen2.5:1.5b` | Agent LLM (Ollama) |
| `AGENT_MAX_ITERATIONS` | `5` | Max agent reasoning steps |
| `BILLING_PROVIDER` | `mock` | `mock` \| `stripe` |
| `STRIPE_SECRET_KEY` | *(empty)* | Stripe secret (provider=stripe only) |
| `OTEL_ENABLED` | `false` | Enable OTLP trace export |

---

## Admin Console

The Next.js 15 admin console lives in `apps/admin/` and runs on `http://localhost:3001`.

| Route | Purpose |
|---|---|
| `/console` | Dashboard — metrics, risk gauge, activity |
| `/console/tenants` | Tenant management |
| `/console/rag` | Upload docs, ask questions, list indexed files |
| `/console/vision` | Upload images, receive AI analysis |
| `/console/agent` | Dispatch tasks to agent, inspect tool calls |
| `/console/billing` | Subscription, quota, invoices, plan upgrade |
| `/console/observability` | Prometheus metrics, health |
| `/console/security` | Security events |
| `/console/airlock` | SQL Airlock decisions |
| `/console/settings` | Settings |

### DemoAuthBar

Every API-connected page shows an amber/green config bar at the top. Set:
- **JWT Token** — output of the generation command above
- **Project ID** — `22222222-2222-2222-2222-222222222222`

The bar turns green when both are set. Values persist in `localStorage`.

---

## Database Migrations

```bash
alembic upgrade head          # apply all pending
alembic current               # show current revision
alembic revision --autogenerate -m "describe change"
alembic downgrade -1          # roll back one step
alembic history --verbose
```

Migrations run automatically on container startup via `docker/entrypoint.sh`.

---

## Docker

```bash
cp .env.example .env
docker compose up --build     # first run — builds image and starts postgres + api
docker compose up             # subsequent runs
docker compose down           # stop (keeps postgres volume)
docker compose down -v        # full teardown including database volume
```

API available at `http://localhost:8000`.

### Smoke test (no postgres needed)

```bash
docker build -t mythos-aegis:local .
docker run --rm --entrypoint whoami mythos-aegis:local   # must print: appuser
docker run -d --name smoke -e APP_ENV=development \
  -e JWT_SECRET=smoke-test-key-not-for-real-use \
  -p 8000:8000 --entrypoint python mythos-aegis:local \
  -m uvicorn app.main:app --host 0.0.0.0 --port 8000
curl -s http://localhost:8000/health/live    # {"status": "ok"}
docker stop smoke && docker rm smoke
```

---

## Kubernetes

Manifests in `k8s/`. See full deploy, rollout, rollback, and scaling commands in
[docs/disaster-recovery.md](docs/disaster-recovery.md).

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/pdb.yaml
kubectl rollout status deployment/mythos-aegis -n mythos-aegis
```

---

## Security

- **JWT** — HS256 Bearer; all claims verified before payload inspection; raw token never logged
- **Key rotation** — zero-downtime via `KeyRotationService`; previous key accepted until expiry
- **RBAC** — permissions checked per-endpoint (`rag.upload`, `vision.analyze`, `agent.run`, …)
- **Multi-tenancy** — every DB query scoped to `tenant_id` from verified JWT claims
- **SQL Airlock** — multi-stage validation; query fingerprint logged, never raw SQL
- **Rate limiting** — per-tenant Redis windows; fail-open if Redis unavailable
- **Container** — non-root (`appuser` UID 1001); no secrets baked into image
- **Production guard** — app refuses to start if `JWT_SECRET` is the dev default

---

## Observability

### Health

| Endpoint | Kubernetes probe |
|---|---|
| `GET /health/live` | Liveness |
| `GET /health/ready` | Readiness (DB ping) |
| `GET /health/startup` | Startup |

### Prometheus metrics (`GET /metrics`)

All names use the `mythos_` prefix: `http_requests_total`, `http_request_duration_seconds`,
`pathway_requests_total`, `sql_airlock_rejections_total`, `auth_failures_total`,
`rate_limit_hits_total`, `secret_rotation_total`.

### OpenTelemetry

```bash
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-collector:4318/v1/traces
OTEL_SERVICE_NAME=mythos-aegis
```

---

## Release Checklist

- [ ] All three CI workflows pass (CI, Docker, Security)
- [ ] `./scripts/verify.sh --security` passes locally
- [ ] Coverage ≥ 80% (`pytest --cov=app --cov-fail-under=80`)
- [ ] No bandit medium/high findings
- [ ] No dependency CVEs (`pip-audit --skip-editable`)
- [ ] No new secrets (`detect-secrets scan --baseline .secrets.baseline`)
- [ ] `.env.example` up to date
- [ ] `JWT_SECRET` ≥ 32 chars, not the dev default, stored in a secret manager
- [ ] Non-root container: `docker run --rm --entrypoint whoami <image>` → `appuser`
- [ ] `alembic upgrade head` applied
- [ ] `/health/ready` returns `{"status": "ready"}`
- [ ] Admin console builds: `cd apps/admin && npm run build`
