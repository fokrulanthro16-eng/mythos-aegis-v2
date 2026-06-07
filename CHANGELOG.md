# Changelog

All notable changes to Mythos Aegis are documented in this file.

---

## [0.4.0] — 2026-06-07

### Added
- **Admin Console** (`apps/admin/`) — Next.js 15 premium dark console with animated landing page,
  10 console routes (Dashboard, RAG, Vision, Agent, Billing, Observability, Security, SQL Airlock,
  Tenants, Settings), and a `DemoAuthBar` on every API page
- **CORS** — `CORSMiddleware` as outermost Starlette middleware; enables browser-based admin UI
  to reach the API without preflight failures
- **RAG pipeline page** — upload, document list, semantic search, grounded Q&A with citations
- **Vision analysis page** — image upload, prompt, structured AI response
- **Agent runner page** — stateless run and multi-turn sessions; tool-call trace display
- **Billing page** — quota widget, mock plan activation, cancel, invoices
- **`.env.example`** — complete environment reference covering all 30+ config vars including
  `JWT_PREVIOUS_SECRET`, `JWT_ALGORITHM`, corrected `RAG_MAX_FILE_SIZE_MB` and `VISION_MAX_IMAGE_SIZE_MB`
- **`docs/DEMO.md`** — 15-minute step-by-step demo walkthrough (JWT generation, DemoAuthBar,
  all four AI domains, curl verification, troubleshooting)
- **`docs/PROJECT_STATUS.md`** — per-subsystem status table, coverage summary, architecture snapshot
- **`docs/release/`** — `SCREENSHOT_CHECKLIST.md`, `RELEASE_NOTES.md`, `PORTFOLIO_SUMMARY.md`

### Fixed
- **SVG hydration mismatch** (`apps/admin/components/risk-prediction.tsx`) — `RiskGauge` arc path
  moved to module scope with `.toFixed(4)` rounding; eliminates Node.js / browser float-string divergence
- **`pypdf` missing from venv** — package was in `pyproject.toml` but not installed; all 926 tests now pass
- **Billing page endpoint mismatch** — rewrote `console/billing/page.tsx` with correct paths
  (`/v1/billing/quota`, two-step checkout/activate, `DELETE /v1/billing/subscription`)
- **`pyproject.toml`** — version `0.1.0` → `0.4.0`; description updated from "Phase 1 intent parser"
  to reflect full platform scope

### Changed
- **README** — complete rewrite from "Enterprise Intent Parser" to "Multi-tenant AI SaaS Platform";
  all 16 primary endpoints documented and verified
- **`app/main.py`** — version `0.4.0`; description updated; `CORSMiddleware` added as outermost layer

---

## [0.3.0] — prior

Workflow engine, SaaS tenant/project/API-key management, observability (Prometheus + OTEL), 
Docker + Kubernetes manifests, CI/CD pipelines (ci.yml, docker.yml, security.yml).

---

## [0.2.0] — prior

RAG pipeline, Vision intelligence, Agent runtime, metered billing (mock + Stripe config),
JWT key rotation, Redis rate limiting, Alembic migrations (8 revisions).

---

## [0.1.0] — prior

Deterministic intent parser, SQL Airlock, multi-tenant DB schema, JWT auth + RBAC middleware.
