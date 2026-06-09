# Demo Script — Mythos Aegis v0.5.0-demo

**Audience:** Mentor / technical reviewer  
**Duration:** 20 minutes (full) · 10 minutes (abbreviated)  
**Goal:** Walk through four AI capability domains, show the security boundary, and
demonstrate cloud-native engineering discipline.

---

## Setup (do before the session)

### 1. Start the stack

```powershell
# Terminal 1 — backend
uvicorn app.main:app --port 8000

# Terminal 2 — admin console
cd apps/admin; npm run dev    # → http://localhost:3001

# Terminal 3 — keep free for curl commands
```

Verify backend is up:
```powershell
curl http://localhost:8000/health
# → {"status": "ok"}
```

### 2. Generate the demo JWT

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
print(jwt.encode(payload,'mythos-aegis-dev-secret-change-in-production',algorithm='HS256'))
"
```

Copy the `eyJ…` output. Set it:

```powershell
$TOKEN = "eyJ..."
```

### 3. Prepare demo files

- `demo.txt` — any plain text, e.g.:
  ```
  Mythos Aegis is a multi-tenant AI SaaS platform with RAG, Vision, Agent, and Billing.
  JWT authentication scopes every request to the authenticated tenant.
  ```
- `photo.jpg` — any JPEG (phone photo, product image, screenshot)

---

## Part 1 — Quality gates (2 min)

**Talking point:** "Before anything else — zero lint errors, zero type errors, 961 tests
passing. This is the baseline I enforce on every commit."

```powershell
python -m ruff check app/    # All checks passed
python -m mypy app/          # Success: no issues found in 206 source files
python -m pytest -q          # 961 passed, 0 failures
```

**What to show:** All three commands exit 0. Point out the test count.

---

## Part 2 — Health and observability (2 min)

**Talking point:** "The API has three K8s probe endpoints and two operational endpoints. None
require authentication — they're exempt from JWT and rate-limit middleware explicitly."

```powershell
# Liveness — K8s tells the cluster the pod is alive
curl http://localhost:8000/health/live

# Readiness — K8s only sends traffic when this returns 200
curl http://localhost:8000/health/ready

# Service status — human-readable, includes git version tag
curl http://localhost:8000/status
```

Expected `/status` response:
```json
{
  "service": "mythos-aegis",
  "version": "v0.5.0-demo",
  "database": "connected",
  "redis": "disconnected"
}
```

**What to highlight:** `redis: "disconnected"` is honest — the platform degrades gracefully
rather than hiding the state. Rate limiting fails open; the app keeps running.

---

## Part 3 — RAG pipeline (5 min)

**Talking point:** "Upload a document, chunk it, embed it via Ollama nomic-embed-text,
store the 768-dimension vector in pgvector on Supabase. Then semantic search and grounded
Q&A — the answer is cited back to the source chunk."

### 3a. Upload

```powershell
curl -X POST http://localhost:8000/v1/rag/upload `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@demo.txt" `
  -F "project_id=22222222-2222-2222-2222-222222222222"
```

Expected:
```json
{"status": "indexed", "chunk_count": 1, "document_id": "..."}
```

**What to highlight:** The file is chunked (512 tokens, 50-token overlap), each chunk
embedded via Ollama, the embedding stored as `vector(768)` in Supabase.

### 3b. Semantic search

```powershell
curl -X POST http://localhost:8000/v1/rag/search `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"query":"authentication","project_id":"22222222-2222-2222-2222-222222222222"}'
```

**What to highlight:** The query is embedded the same way; the SQL uses pgvector's `<=>` cosine
operator to rank chunks. Point to the score values — lower is more similar.

### 3c. Grounded Q&A

```powershell
curl -X POST http://localhost:8000/v1/rag/ask `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{
    "question": "How does Mythos Aegis handle authentication?",
    "project_id": "22222222-2222-2222-2222-222222222222"
  }'
```

Expected: an answer grounded in the uploaded text, with `citations` pointing to the
source `chunk_id` and `filename`.

### 3d. Show the admin UI

Open **http://localhost:3001/console/rag**

1. Paste JWT + project ID into the amber DemoAuthBar → turns green
2. Show the document list with the uploaded file
3. Type the same question in the UI — show the cited answer

**Supabase pgvector proof** (if asked):

```sql
-- Run in Supabase SQL Editor
SELECT pg_typeof(embedding) FROM document_chunks LIMIT 1;
-- → vector

SELECT indexname FROM pg_indexes WHERE tablename='document_chunks';
-- → ix_chunk_embedding_ivfflat
```

---

## Part 4 — Gemini Cloud Vision (4 min)

**Talking point:** "The vision system has a provider abstraction. The Ollama provider uses a
local model. The Gemini provider calls the REST API via httpx — no Google SDK, no new
dependency. If the API key is missing, the endpoint returns 503 and the rest of the
application keeps running."

### 4a. Structured analysis (with key set)

```powershell
curl -X POST http://localhost:8000/vision/analyze `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@photo.jpg"
```

Expected:
```json
{
  "summary": "A photograph showing...",
  "detected_objects": ["person", "table", "laptop"],
  "observations": ["The room is well-lit.", "Text visible on the screen."]
}
```

**What to highlight:** The output schema is fixed and structured — not a free-text blob.
The Gemini `response_mime_type: "application/json"` generation config ensures the model
returns parseable JSON.

### 4b. Graceful degradation (without key)

Temporarily unset the key:

```powershell
$saved = $env:GEMINI_API_KEY
$env:GEMINI_API_KEY = ""

curl -X POST http://localhost:8000/vision/analyze `
  -H "Authorization: Bearer $TOKEN" `
  -F "file=@photo.jpg"
# → 503 {"detail": "GEMINI_API_KEY is not configured..."}

curl http://localhost:8000/health
# → 200 {"status": "ok"}  ← app is still running

$env:GEMINI_API_KEY = $saved
```

**What to highlight:** 503, not 500. The application does not crash. Other endpoints are
unaffected. This is the `VisionProviderUnavailableError` path — a deliberate exception
type, not an unhandled runtime error.

---

## Part 5 — Security boundary (3 min)

**Talking point:** "Three things I'll show: JWT validation, token never logged, and the
production startup guard."

### 5a. Unauthenticated request

```powershell
curl -v http://localhost:8000/v1/rag/search `
  -H "Content-Type: application/json" `
  -d '{"query":"test","project_id":"22222222-2222-2222-2222-222222222222"}'
# → 401 Unauthorized
```

**What to highlight:** The 401 is returned by `JWTAuthMiddleware` before the route handler
runs. No DB query is made.

### 5b. Token redacted in logs

Point to the terminal running uvicorn. Show the structured JSON log line for the previous
authenticated request — the `authorization` field reads `"[REDACTED]"`.

### 5c. Production startup guard

```powershell
$env:APP_ENV = "production"
$env:JWT_SECRET = "mythos-aegis-dev-secret-change-in-production"
uvicorn app.main:app
# → pydantic_core.ValidationError: JWT_SECRET must be a strong secret (≥32 chars...)
$env:APP_ENV = "development"
$env:JWT_SECRET = ""  # reset to .env default
```

**What to highlight:** The app refuses to start — not just a warning, a hard validation
failure at settings load time.

---

## Part 6 — Billing lifecycle (2 min, if time allows)

**Talking point:** "Mock provider, same state machine as Stripe. The `BILLING_PROVIDER`
env var switches providers — the billing logic doesn't know which one it's talking to."

```powershell
# Plans — public, no auth
curl http://localhost:8000/v1/billing/plans

# Checkout
curl -X POST http://localhost:8000/v1/billing/checkout `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"plan":"pro"}'

# Activate (paste session_id from above)
curl -X POST http://localhost:8000/v1/billing/checkout/activate `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"session_id":"<SESSION_ID>"}'

# Confirm active
curl http://localhost:8000/v1/billing/subscription `
  -H "Authorization: Bearer $TOKEN"
# → {"plan": "pro", "status": "active", ...}

# Cancel
curl -X DELETE http://localhost:8000/v1/billing/subscription `
  -H "Authorization: Bearer $TOKEN"
```

---

## Abbreviated demo (10 min)

If time is short, cover these three:

1. **Quality gates** (Part 1) — 2 min
2. **RAG pipeline** (Part 3a + 3c) — 4 min
3. **Gemini Vision + graceful degradation** (Part 4a + 4b) — 4 min

Skip Parts 2, 5, 6.

---

## Anticipated questions

| Question | Prepared answer |
|---|---|
| "Why not OpenAI for embeddings?" | "Ollama keeps everything local for the demo. The provider abstraction in `app/ai_gateway/` and `app/vision/providers/` makes swapping trivial — it's on the v0.6 roadmap." |
| "How does tenant isolation work?" | "Every request carries a JWT. The middleware extracts `tenant_id` from the verified claims and attaches it to a `SecurityContext`. Every DB query adds `.where(Model.tenant_id == ctx.tenant_id)` — the ORM enforces it." |
| "What happens if pgvector is down?" | "The `USE_PGVECTOR` flag switches the search path. With it false, the code falls back to numpy cosine similarity in Python. Degraded performance, no crash." |
| "Is the Gemini API key safe?" | "It's read from the environment only — never in code, never logged. The httpx call passes it as a query parameter; we log the HTTP status, not the URL." |
| "What's the weakest part?" | "`workflow/service.py` has 35% test coverage — the lowest in the codebase. The step engine is implemented; the integration tests are the gap. It's v0.6 P1." |
| "How do you handle Redis being down?" | "Rate limiting fails open — requests are allowed through with a warning log. This is intentional: Redis becoming a hard SPoF in front of every request is worse than temporarily relaxed limits." |
