# Release Notes — Mythos Aegis v0.4.0

**Release date:** 2026-06-07  
**Overall production-demo readiness:** ~90%

---

## What changed in v0.4.0

This release completes the platform integration and ships a fully functional local demo with
a premium admin console, end-to-end API wiring, and a hardened security boundary.

### New in this release

#### Admin Console (apps/admin)
- Full **Next.js 15** dark console with 9 console routes and a sidebar nav
- **DemoAuthBar** on every API page — amber/green config bar persisting JWT and Project ID to
  `localStorage`; no manual header injection required
- **RAG Pipeline page** — upload, document list, semantic search, grounded Q&A with citations
- **Vision Analysis page** — image upload, prompt input, structured AI response
- **Agent Runner page** — task dispatch, tool-call trace, iteration count
- **Billing page** — quota widget, feature flags, mock plan upgrade, cancel, invoice list
- **Observability page** — health status and Prometheus metrics
- **Security Events / SQL Airlock / Tenants / Settings** pages

#### Backend
- **CORS** — `CORSMiddleware` added as outermost Starlette middleware; fixes browser preflight
  returning 401 before JWT middleware fires
- **Version** bumped to `0.4.0` in `app/main.py` and `pyproject.toml`
- **Description** updated in `pyproject.toml` to reflect the full platform scope
- **`app/main.py` description** updated from "Phase 1 intent parser" to "AI SaaS platform"

#### Billing
- Billing page rewritten with correct endpoint paths (`/v1/billing/quota`, `/v1/billing/checkout`,
  `/v1/billing/checkout/activate`, `DELETE /v1/billing/subscription`)
- Two-step mock activation flow: `POST /checkout` → `POST /checkout/activate`
- `StatusBadge` component for subscription and invoice status display

#### Bug fixes
- **SVG hydration mismatch** (`risk-prediction.tsx`) — `RiskGauge` arc path constants moved to
  module scope with `.toFixed(4)` rounding; eliminates server/client float-string divergence
- **`pypdf` module** — `pypdf>=4.0.0` was in `pyproject.toml` but not installed in the venv;
  added to ensure all 926 tests pass

#### Configuration
- **`.env.example`** — added `JWT_PREVIOUS_SECRET`, `JWT_ALGORITHM`, corrected
  `RAG_MAX_FILE_SIZE_MB` (was `RAG_MAX_FILE_SIZE_BYTES`), corrected
  `VISION_MAX_IMAGE_SIZE_MB` (was `VISION_MAX_IMAGE_SIZE_BYTES`); added full sections for
  Ollama, RAG, Vision, Agent, Workflow, Billing vars

#### Documentation
- **README** — complete rewrite from "Enterprise Intent Parser" to "Multi-tenant AI SaaS Platform";
  all 16 primary endpoints documented and verified against actual routes
- **docs/DEMO.md** — 15-minute step-by-step demo script with JWT generation (Windows + Linux),
  DemoAuthBar setup, RAG/Vision/Agent/Billing walkthrough, curl examples, troubleshooting table
- **docs/PROJECT_STATUS.md** — per-subsystem status table, test coverage summary, known gaps,
  architecture snapshot

---

## Test metrics

| Metric | Value |
|---|---|
| Total tests | 926 |
| Failures | 0 |
| Coverage | 89% (5042 statements) |
| CI minimum | 80% |
| Lint | ruff: 0 issues (203 files) |
| Type check | mypy: 0 issues (203 files) |

---

## Known gaps (path to 95%)

1. **Screenshots** — no captured screenshots of running stack; see `docs/release/SCREENSHOT_CHECKLIST.md`
2. **Ollama e2e in CI** — RAG/Vision/Agent tests mock the Ollama client; no live inference in CI
3. **Stripe e2e** — Stripe integration is config-only (`BILLING_PROVIDER=stripe`); not tested
   against the Stripe API
4. **`workflow/service.py` coverage** — 35% (lowest in codebase); acceptable for RC but noted

---

## Security notes

- `JWT_SECRET` defaults to a clearly labelled dev value; production startup guard refuses to boot
  if the dev default is used with `APP_ENV=production`
- All image bytes, vision output, and prompt content are excluded from logs
- `STRIPE_SECRET_KEY` never echoed to any logger
- Container runs as non-root (`appuser`, UID 1001)

---

## Upgrade notes

- **`.env`** — if copying from a previous `.env.example`, add:
  ```
  JWT_PREVIOUS_SECRET=
  JWT_ALGORITHM=HS256
  RAG_MAX_FILE_SIZE_MB=10
  VISION_MAX_IMAGE_SIZE_MB=20
  ```
  Remove any stale `RAG_MAX_FILE_SIZE_BYTES` or `VISION_MAX_IMAGE_SIZE_BYTES` entries.
- **Migrations** — run `alembic upgrade head` after pulling this release.
- **Admin console** — run `npm install` in `apps/admin/` before `npm run dev` or `npm run build`.
