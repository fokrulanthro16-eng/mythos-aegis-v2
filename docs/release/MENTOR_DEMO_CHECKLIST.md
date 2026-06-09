# Mentor Demo Checklist — Mythos Aegis v0.5.0-demo

Run these checks in order before and during the demo session.  
Each item is a binary gate: pass or explain.

---

## Before the session (10 min setup)

### Quality gates — run fresh

```powershell
# From repo root, venv active
python -m ruff check app/           # expect: All checks passed
python -m mypy app/                 # expect: Success: no issues found in 206 source files
python -m pytest --tb=short -q      # expect: 961 passed, 0 failures
```

- [ ] `ruff` — **0 issues, 206 files**
- [ ] `mypy` — **0 issues, 206 files**
- [ ] `pytest` — **961 passed, 0 failures**
- [ ] Coverage ≥ 80% (run `pytest --cov=app --cov-report=term-missing | tail -5`)

### Git state

```powershell
git log --oneline -6
git status
git tag | Select-String "demo"
```

- [ ] Working tree clean (`nothing to commit`)
- [ ] Tag `v0.5.0-demo` present and pushed to origin
- [ ] Last 6 commits visible (see expected log below)

Expected recent log:
```
d18cf44 feat(vision): add Gemini Vision provider
6f00531 feat(api): add health and status endpoints
395491e fix(e2e): correct health URL, JWT iat claim, and non-blocking stderr drain
23ffa5f feat(rag): wire pgvector SQL similarity search into DocumentChunkRepository
8a76005 feat(db): Supabase pgvector integration — migrations applied, RAG smoke test 7/7
0dd4233 feat(db): add Supabase pgvector support
```

### Admin console build

```powershell
cd apps/admin; npm run build
```

- [ ] Build exits 0 with no TypeScript errors

---

## Infrastructure checklist

### Local stack (for full demo)

- [ ] PostgreSQL running on `localhost:5432` (or Supabase URL configured in `.env`)
- [ ] Ollama running: `ollama serve` → `curl http://localhost:11434/api/tags`
- [ ] Models pulled:
  - [ ] `ollama pull qwen2.5:1.5b` (agent + Q&A)
  - [ ] `ollama pull nomic-embed-text` (embeddings)
  - [ ] `ollama pull qwen2.5-vl:7b` (local vision)
- [ ] Backend started: `uvicorn app.main:app --port 8000`
- [ ] Admin console started: `cd apps/admin && npm run dev` (port 3001)

### Supabase pgvector (if demoing cloud RAG)

- [ ] `USE_PGVECTOR=true` and `DB_SSL_REQUIRE=true` in `.env`
- [ ] `DATABASE_URL` points to Supabase Session Pooler
- [ ] `alembic upgrade head` applied — column is `vector(768)`
- [ ] Verify: `SELECT pg_typeof(embedding) FROM document_chunks LIMIT 1;` → `vector`
- [ ] IVFFlat index present: `SELECT indexname FROM pg_indexes WHERE tablename='document_chunks';`

### Gemini Cloud Vision (if demoing cloud vision)

- [ ] `GEMINI_API_KEY` set in `.env` (never committed)
- [ ] `GEMINI_MODEL=gemini-2.0-flash`
- [ ] Test: `POST /vision/analyze` with a JPEG → 200 with `{summary, detected_objects, observations}`
- [ ] Without key: endpoint returns **503**, application continues running (graceful degradation)

---

## Security review gates

These are the items a code-quality reviewer will check. Know the answers before they ask.

| Question | Answer / Location |
|---|---|
| Where is the JWT token validated? | `app/auth/jwt.py` — `validate_token()`, atomic `jwt.decode()` |
| Can a request access another tenant's data? | No — every query has `.where(Model.tenant_id == ctx.tenant_id)` |
| Is the raw JWT ever logged? | No — `app/observability/middleware.py` replaces it with `[REDACTED]` |
| What happens if `JWT_SECRET` is the dev default in production? | App refuses to start — `app/core/config.py` `validate_production_secrets()` |
| Where is the Gemini API key? | Environment only; never in code, never logged, never committed |
| What happens if Redis is down? | Rate limiting fails open — no requests blocked, ~1s latency logged |
| What happens if pgvector is missing? | Falls back to numpy cosine similarity; no crash |
| What happens if `GEMINI_API_KEY` is missing? | `POST /vision/analyze` returns 503; rest of app unaffected |
| Are SQL queries logged? | SHA-256 fingerprint only — `app/pathways/sql_airlock/` |

### Startup guard demo (optional live check)

```powershell
$env:APP_ENV = "production"
$env:JWT_SECRET = "mythos-aegis-dev-secret-change-in-production"
uvicorn app.main:app
# Expected: pydantic ValidationError — "JWT_SECRET must be a strong secret"
```

Reset after: `$env:APP_ENV = "development"`

---

## Endpoint walkthrough

### Health probes (no auth)

```powershell
curl http://localhost:8000/health
# → {"status": "ok"}

curl http://localhost:8000/status
# → {"service": "mythos-aegis", "version": "v0.5.0-demo", "database": "connected", "redis": "disconnected"}

curl http://localhost:8000/health/live
# → {"status": "ok"}

curl http://localhost:8000/health/ready
# → {"status": "ready", "database": "ok"}
```

- [ ] `/health` → 200
- [ ] `/status` → 200 with all four fields present
- [ ] `/health/live` → 200
- [ ] `/health/ready` → 200 with real DB

### JWT generation

```powershell
python -c "
import jwt, time
payload = {
    'sub': '11111111-1111-1111-1111-111111111111',
    'tenant_id': '11111111-1111-1111-1111-111111111111',
    'iss': 'mythos-aegis', 'aud': 'mythos-aegis-api',
    'iat': int(time.time()), 'exp': int(time.time()) + 86400,
    'roles': ['admin'],
    'permissions': ['rag.upload','rag.search','rag.ask',
                    'vision.analyze','vision.extract',
                    'agent.run','billing.read','billing.manage'],
}
print(jwt.encode(payload, 'mythos-aegis-dev-secret-change-in-production', algorithm='HS256'))
"
```

Set `TOKEN=<output>` for subsequent curl commands.

### RAG pipeline

```powershell
# Upload
curl -X POST http://localhost:8000/v1/rag/upload `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@demo.txt" `
  -F "project_id=22222222-2222-2222-2222-222222222222"
# → {"status": "indexed", "chunk_count": N, "document_id": "..."}

# Ask (requires Ollama running)
curl -X POST http://localhost:8000/v1/rag/ask `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"question":"What is Mythos Aegis?","project_id":"22222222-2222-2222-2222-222222222222"}'
# → {"answer": "...", "citations": [...]}
```

- [ ] Upload → `status: "indexed"`
- [ ] Ask → answer + citations

### Gemini Cloud Vision

```powershell
curl -X POST http://localhost:8000/vision/analyze `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@photo.jpg"
# → {"summary": "...", "detected_objects": [...], "observations": [...]}
```

- [ ] Returns 200 with all three structured fields
- [ ] Without `GEMINI_API_KEY`: returns 503, not 500

### Billing lifecycle

```powershell
# Plans (public)
curl http://localhost:8000/v1/billing/plans

# Quota (authenticated)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/billing/quota

# Checkout
curl -X POST -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"plan":"pro"}' http://localhost:8000/v1/billing/checkout

# Activate (use session_id from checkout response)
curl -X POST -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"session_id":"<from above>"}' http://localhost:8000/v1/billing/checkout/activate

# Cancel
curl -X DELETE -H "Authorization: Bearer $TOKEN" `
  http://localhost:8000/v1/billing/subscription
```

- [ ] Plans public → 4 plans returned without JWT
- [ ] Checkout → session ID
- [ ] Activate → subscription shows `pro`, `active`
- [ ] Cancel → subscription shows `cancelled`

---

## Admin console walkthrough

Open **http://localhost:3001**

- [ ] Landing page loads without errors
- [ ] Navigate to `/console/rag` — amber DemoAuthBar visible
- [ ] Paste JWT + project ID `22222222-2222-2222-2222-222222222222` → bar turns green
- [ ] RAG: upload a `.txt` file → success toast
- [ ] RAG: click Refresh → document appears in list
- [ ] RAG: type a question → answer + citations displayed
- [ ] Vision (`/console/vision`): upload a JPEG → analysis displayed
- [ ] Agent (`/console/agent`): run a task → tool-call trace visible
- [ ] Billing (`/console/billing`): quota widget shows FREE
- [ ] Billing: Mock Activate `pro` → status updates to active
- [ ] Billing: Cancel → status updates to cancelled
- [ ] Observability (`/console/observability`): health check green

---

## Known gaps to acknowledge

State these proactively — they demonstrate engineering maturity, not incompleteness.

| Gap | What to say |
|---|---|
| Ollama not in CI | "All AI tests mock the HTTP client. A CI job with an Ollama sidecar is on the v0.6 roadmap." |
| Redis not deployed | "Rate limiting fails open by design — Redis becoming a hard SPoF would be worse. The Lua script is correct; it just needs deployment." |
| `workflow/service.py` 35% coverage | "The step engine is fully implemented; the integration tests are the gap. It's the lowest-coverage module and I've noted it explicitly." |
| pgvector missing locally | "The migration and search code are validated against Supabase. Local PG18 doesn't ship pgvector; fallback to numpy is intentional." |
| Stripe not exercised | "Stripe integration is config-complete. `BILLING_PROVIDER=stripe` plus real keys would activate it. The mock provider tests the same state machine." |
| Screenshots not captured | "The checklist exists. I need a running stack with real data to capture them." |
