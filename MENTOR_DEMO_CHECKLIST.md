# Mythos Aegis — Mentor Demo Checklist

Use this before and during the demo session to ensure nothing is missed.
Check each item as you go. Items marked **(backup)** have screenshot fallbacks.

---

## Before Demo

- [ ] Repo is on branch `main` and up to date with `origin/main`
- [ ] Working tree is clean (`git status` → nothing to commit)
- [ ] `.env` file exists and contains:
  - [ ] `VISION_PROVIDER=fallback` (no Gemini key needed)
  - [ ] `BILLING_PROVIDER=mock` (no Stripe key needed)
  - [ ] `DATABASE_URL` pointing to Supabase or local Postgres
  - [ ] `USE_PGVECTOR=true` if on Supabase with pgvector enabled
- [ ] Backend starts cleanly:
  ```
  python -m uvicorn app.main:app --reload --port 8000
  ```
  Check for `startup vision_provider=fallback` in the log
- [ ] Admin console starts:
  ```
  cd apps/admin && npm run dev
  ```
  Opens at `http://localhost:3001`
- [ ] DemoAuthBar configured in the console:
  - [ ] JWT Token pasted (generate with the README command)
  - [ ] Project ID set to `22222222-2222-2222-2222-222222222222`
  - [ ] Bar is **green**
- [ ] Test PDF or text file ready to upload for RAG demo
- [ ] Screenshots folder open as backup: `docs/screenshots/`

---

## Live Demo Checklist

### Health and Status
- [ ] Open browser or terminal — show `GET /health` → `{"status": "ok"}`
- [ ] Show `GET /status` → `service`, `version`, `database`, `redis` all present
- **(backup)** `docs/screenshots/health-endpoint.png`, `status-endpoint.png`

### Auth and RBAC
- [ ] Show JWT generation command from README
- [ ] Paste token into DemoAuthBar — confirm bar turns green
- [ ] Briefly explain: HS256, claims checked, raw token never logged
- [ ] Mention permission names: `rag.upload`, `vision.analyze`, `agent.run`

### SQL Airlock
- [ ] Navigate to `/console/airlock` in admin console
- [ ] Explain the three stages: fingerprint → intent → injection check

### RAG Upload and Ask
- [ ] Navigate to `/console/rag`
- [ ] Upload a PDF or text file — confirm chunk count in response
- [ ] Ask a question — confirm answer appears with source citations
- **(backup)** `docs/screenshots/rag-query-result.png`

### Vision Fallback
- [ ] Navigate to `/console/vision`
- [ ] Upload any image — confirm response includes `summary`, `detected_objects`, `observations`
- [ ] Point out `"provider": "fallback"` in the response — no external service called
- **(backup)** `docs/screenshots/vision-analyze-fallback.png`

### Supabase pgvector
- [ ] Mention `USE_PGVECTOR=true` and Supabase connection
- **(backup)** `docs/screenshots/supabase-pgvector-setup.png` — shows pgvector extension confirmed

---

## Evidence Checklist

- [ ] README — Architecture, Features, Environment, Demo Screenshots, Test Evidence, Release Status all visible
- [ ] `FINAL_SUBMISSION_REPORT.md` — open and ready to show
- [ ] Test Evidence table in README shows:
  - [ ] Ruff passing
  - [ ] Mypy passing
  - [ ] Pytest 980+ passed, 0 failures
  - [ ] GitHub Actions `ci.yml` green
  - [ ] GitHub Actions `docker.yml` green
  - [ ] GitHub Actions `security.yml` green
- [ ] All five screenshots visible and non-blank in `docs/screenshots/`

---

## Backup Plan

If the live backend cannot start:

- [ ] Use screenshots for all API/endpoint demos
- [ ] Walk through the README Architecture and Features sections
- [ ] Show `FINAL_SUBMISSION_REPORT.md` as the written evidence package
- [ ] Show the `DEMO_SCRIPT.md` narrative as a spoken walkthrough
- [ ] Open `app/vision/providers/fallback_vision.py` to show the fallback implementation
- [ ] Open `app/rag/routes.py` to show the ask endpoint with citations

If Supabase is unavailable:

- [ ] Set `DATABASE_URL` to local Postgres, `USE_PGVECTOR=false`
- [ ] RAG still works with `ARRAY(Float)` embeddings (numpy cosine search)
- [ ] Show `docs/screenshots/supabase-pgvector-setup.png` for pgvector evidence

---

## Final Submission Checklist

- [ ] `FINAL_SUBMISSION_REPORT.md` committed and pushed to `main`
- [ ] `DEMO_SCRIPT.md` committed and pushed to `main`
- [ ] `MENTOR_DEMO_CHECKLIST.md` committed and pushed to `main`
- [ ] All five screenshots committed and pushed to `main`
- [ ] README polished and pushed to `main`
- [ ] `git log --oneline -5` confirms all commits present on `main`
- [ ] GitHub repo URL shared with mentor
- [ ] Branch is `main` — not a feature branch or draft PR
