# Mythos Aegis — Project Status

Last updated: 2026-06-09

---

## Overall readiness: 72% production / 87% portfolio-demo

> See [`docs/release/PRODUCTION_READINESS_REVIEW.md`](release/PRODUCTION_READINESS_REVIEW.md) for
> the full mentor review document with checklist and gap analysis produced on 2026-06-08.

| Area | Status | Notes |
|---|---|---|
| Backend API | **Complete** | 961 tests, all passing |
| JWT auth + RBAC | **Complete** | Zero-downtime key rotation |
| RAG pipeline | **Complete** | Requires Ollama + Postgres |
| Vision analysis | **Complete** | Requires Ollama vision model |
| Gemini Cloud Vision | **Complete** | `POST /vision/analyze` — set `GEMINI_API_KEY`; graceful 503 without it |
| Agent runtime | **Complete** | Requires Ollama |
| Billing (mock) | **Complete** | No external deps |
| Billing (Stripe) | **Config only** | Set `BILLING_PROVIDER=stripe` + keys |
| Workflow engine | **Complete** | |
| Admin console | **Complete** | Next.js 15, 10 console routes + landing page, build green |
| CORS | **Complete** | localhost:3000 + 3001 allowed |
| Demo JWT flow | **Complete** | See README §3 |
| .env.example | **Complete** | All vars documented and correct |
| README | **Complete** | Full platform description |
| Docker | **Complete** | Non-root, smoke-tested |
| K8s manifests | **Complete** | 8 manifests, HPA + PDB |
| CI/CD | **Complete** | ci.yml, docker.yml, security.yml |
| Screenshots | **Pending** | Requires running stack |
| Local DB validation | **Complete** | PG18, 26 tables, smoke tested 2026-06-08 |
| pgvector | **Missing** | `double precision[]` fallback; vector search degraded |
| Demo script | **Complete** | See docs/DEMO.md |

---

## Test coverage

```
961 tests, 0 failures, 8 warnings (verified 2026-06-09)
Coverage: 89%+ (above 80% CI minimum)
Ruff:  0 issues
Mypy:  0 issues
Admin: npm run build — green
```

Run: `pytest --cov=app --cov-report=term-missing`

Known low-coverage module: `workflow/service.py` at 35%.

---

## Known gaps / blockers

### Blockers before real production deployment

1. **Push + CI** — Branch is 4 commits ahead of `origin/main`; CI not run on current code.
2. **pgvector** — Not installed; RAG vector search is broken (fallback to `double precision[]`).
3. **Ollama** — Not deployed; RAG, Vision, Agent return empty/503 without it.
4. **Redis** — Not deployed; rate limiting fails open with ~1 s latency per request.
5. **Stripe e2e** — `BILLING_PROVIDER=stripe` path never exercised against real Stripe API.
6. **Secrets management** — K8s `secrets.example.yaml` template only; no real injection workflow.
7. **Staging environment** — No deployment target exists.

### Path to 95% demo-ready

1. **Screenshots** — Start the full stack (Postgres + Ollama + backend + admin) and capture
   screenshots of each console page with real data flowing. Add to `docs/screenshots/`.
2. **Stripe test-mode** — Set `BILLING_PROVIDER=stripe` with a Stripe test key and verify
   the checkout → webhook → activate flow.
3. **Ollama e2e** — Run `scripts/_verify_rag_pipeline.py` against a live Ollama instance.
4. **workflow/service.py** — Bring coverage from 35% to ≥ 70%.

### Resolved this session

- **CORS** — `CORSMiddleware` was missing from `app/main.py`; added as outermost middleware so
  OPTIONS preflight succeeds before `JWTAuthMiddleware` fires.
- **pypdf** — Package listed in `pyproject.toml` but not installed in venv; installed and
  confirmed test passes.
- **Billing page** — Rewrote `apps/admin/app/console/billing/page.tsx` with correct endpoints
  (`/v1/billing/quota`, two-step checkout/activate, `DELETE` cancel).
- **SVG hydration** — Moved `RiskGauge` arc path constants to module scope with `.toFixed(4)`
  rounding; eliminated server/client float-string mismatch.
- **README** — Complete rewrite; describes full AI SaaS platform, not Phase 1 intent parser.
- **.env.example** — Added OLLAMA_*, RAG_*, VISION_*, AGENT_*, WORKFLOW_*, BILLING_* vars;
  fixed `RAG_MAX_FILE_SIZE_MB` (was `_BYTES`) and `VISION_MAX_IMAGE_SIZE_MB` (was `_BYTES`);
  added `JWT_PREVIOUS_SECRET` and `JWT_ALGORITHM`.
- **pyproject.toml** — Bumped `version` to `0.4.0`; updated `description` to match platform scope.
- **docs/release/** — Added `SCREENSHOT_CHECKLIST.md`, `RELEASE_NOTES.md`, `PORTFOLIO_SUMMARY.md`.

---

## Architecture snapshot

```
app/
├── auth/          JWT validation, middleware, RBAC
├── agent/         Tool-calling agent runtime
├── ai_gateway/    Ollama provider + quota enforcement
├── billing/       Plans, subscriptions, mock/Stripe
├── core/          Config, exceptions, security context
├── db/            SQLAlchemy models, session, migrations
├── intent/        Deterministic keyword parser
├── observability/ Health, metrics, tracing, middleware
├── orchestrator   Route dispatch through pathways
├── pathways/      RAG_VISION, SQL_ANALYTICS, etc.
├── rag/           Upload, chunk, embed, search, ask
├── rate_limit/    Redis-backed per-tenant windows
├── response/      ResponsePayload synthesis
├── saas/          Tenants, projects, API keys, audit
├── secrets/       Key rotation service
├── vision/        Image + PDF analysis
└── workflow/      Step engine, retry, timeout

apps/admin/        Next.js 15 admin console
alembic/           8 migration revisions
k8s/               8 Kubernetes manifests
scripts/           verify.sh/.ps1, backup, rag test
```

---

## Dependency notes

| Dependency | Version | Purpose |
|---|---|---|
| FastAPI | ≥0.115 | API framework |
| SQLAlchemy | ≥2.0 | Async ORM |
| asyncpg | ≥0.29 | PostgreSQL async driver |
| PyJWT | ≥2.8 | JWT signing/verification |
| pypdf | ≥4.0 | PDF text extraction |
| numpy | ≥1.26 | Cosine similarity for RAG |
| redis | ≥5.0 | Rate limiting |
| httpx | ≥0.27 | Ollama HTTP client |
| Next.js | 15.5 | Admin console |
