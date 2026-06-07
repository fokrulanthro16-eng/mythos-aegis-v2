# Mythos Aegis — Portfolio Summary

> A production-grade multi-tenant AI SaaS platform built with FastAPI, Next.js 15, and Ollama.

---

## What it is

Mythos Aegis is a full-stack AI SaaS backend + premium admin console that demonstrates
enterprise-grade software engineering across eight distinct capability domains, all running
locally with no cloud dependencies.

---

## Technical highlights

### Backend (FastAPI + Python 3.12)

| Domain | What it does |
|---|---|
| **RAG Pipeline** | Upload → chunk → embed (Ollama nomic-embed-text) → cosine similarity search → cited Q&A via qwen2.5:1.5b |
| **Vision Intelligence** | Binary image upload → Ollama qwen2.5-vl:7b inference → structured response; OCR and PDF extraction |
| **Agent Runtime** | Tool-calling agent loop with structured tool dispatch, iteration tracking, and session persistence |
| **Workflow Engine** | Multi-step step execution with configurable retry, timeout per step, and execution history |
| **Billing** | Full subscription state machine: free → checkout → activate → cancel; mock and Stripe providers |
| **Intent Parser** | Deterministic keyword router → action dispatch → SQL Airlock with multi-stage SQL validation |
| **JWT Auth + RBAC** | HS256 Bearer tokens; zero-downtime key rotation; permissions checked per-endpoint |
| **Observability** | Prometheus metrics, OpenTelemetry tracing, structured JSON logs, three K8s health probes |

### Admin Console (Next.js 15)

A premium dark console at `localhost:3001` with:
- 9 console routes: Dashboard, RAG, Vision, Agent, Billing, Observability, Security, SQL Airlock, Tenants
- **DemoAuthBar** — amber/green config bar on every API page; JWT + Project ID set once, persisted to `localStorage`
- Full end-to-end API wiring: all four AI domains (RAG, Vision, Agent, Billing) callable from the UI

### Security posture

- JWT claims verified before payload inspection; raw token never logged
- Every DB query scoped to `tenant_id` from verified JWT claims (tenant isolation)
- SQL Airlock: fingerprint logged, never raw SQL; injection check at query boundary
- Non-root Docker container (`appuser`, UID 1001); no secrets baked into image
- Production startup guard: app refuses to start if `JWT_SECRET` is the dev default
- Redis-backed per-tenant rate limiting; fail-open when Redis is unavailable

### Infrastructure

- **Docker** — `docker compose up --build`; non-root, smoke-tested in CI
- **Kubernetes** — 8 manifests: Deployment, Service, Ingress, ConfigMap, HPA, PDB, Namespace, Secrets template
- **Alembic** — 8 migration revisions; runs automatically on container startup
- **CI/CD** — 3 GitHub Actions workflows: lint+type+test, Docker smoke, weekly security scan (pip-audit + bandit + detect-secrets)

---

## Metrics

| Metric | Value |
|---|---|
| Tests | 926 passing, 0 failures |
| Coverage | 89% (5042 statements) |
| Source files checked | 203 (ruff + mypy, 0 issues) |
| API endpoints | 30+ across 6 service areas |
| Alembic revisions | 8 |
| K8s manifests | 8 |
| Admin console routes | 9 |
| CI workflows | 3 |

---

## Local demo in 15 minutes

1. Start Postgres + Ollama + backend + admin console
2. Generate a JWT (one Python command, works on Windows + Linux)
3. Paste token + project ID into the amber DemoAuthBar → turns green
4. Upload a document → ask a question → see cited RAG answer
5. Upload an image → see vision AI analysis
6. Run an agent task → inspect tool-call trace
7. Activate a mock billing plan → cancel it → observe state machine
8. `curl /health/live` and `curl /v1/billing/plans` — verify headless API

Full script: [docs/DEMO.md](../DEMO.md)

---

## Stack

**Backend:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (async), asyncpg, Alembic, PyJWT, numpy, httpx, redis, pypdf  
**AI:** Ollama (qwen2.5:1.5b, nomic-embed-text, qwen2.5-vl:7b)  
**Database:** PostgreSQL 15  
**Admin:** Next.js 15, React 19, TypeScript, Tailwind CSS, Framer Motion, Recharts  
**Infra:** Docker, Kubernetes, GitHub Actions, Prometheus, OpenTelemetry  

---

## Repository layout

```
app/                  FastAPI backend (16 modules)
apps/admin/           Next.js 15 admin console
alembic/              8 migration revisions
k8s/                  8 Kubernetes manifests
scripts/              verify.sh/.ps1, backup, RAG smoke test
docs/                 DEMO.md, PROJECT_STATUS.md, disaster-recovery.md
.github/workflows/    ci.yml, docker.yml, security.yml
```
