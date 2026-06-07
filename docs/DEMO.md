# Mythos Aegis — Demo Walkthrough

This guide walks through the complete local demo in ~15 minutes.

---

## Prerequisites checklist

- [ ] PostgreSQL running on `localhost:5432`
- [ ] Ollama running on `localhost:11434`
- [ ] Required models pulled:
  ```bash
  ollama pull qwen2.5:1.5b
  ollama pull nomic-embed-text
  ollama pull qwen2.5-vl:7b
  ```
- [ ] `.env` copied from `.env.example` (defaults work for local demo)
- [ ] `alembic upgrade head` applied
- [ ] Backend running: `uvicorn app.main:app --reload --port 8000`
- [ ] Admin console running: `cd apps/admin && npm run dev`

---

## Step 1 — Generate a demo JWT (do this first)

The token expires in 24 hours. Regenerate it each day.

```powershell
# Windows PowerShell — run from repo root
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
    'iss': 'mythos-aegis', 'aud': 'mythos-aegis-api',
    'iat': int(time.time()), 'exp': int(time.time()) + 86400,
    'roles': ['admin'],
    'permissions': ['rag.upload','rag.search','rag.ask','vision.analyze',
                    'vision.extract','agent.run','agent.sessions.read',
                    'agent.sessions.write','billing.read','billing.manage'],
}
print(jwt.encode(payload, 'mythos-aegis-dev-secret-change-in-production', algorithm='HS256'))
"
```

Copy the output — it's a long `eyJ…` string.

---

## Step 2 — Configure the admin console

Open **http://localhost:3001** and navigate to any API page (e.g. `/console/rag`).

An amber bar appears at the top: **DEMO SETUP REQUIRED**.

Click **configure**, paste:
- **JWT Token** — the `eyJ…` string from step 1
- **Project ID** — `22222222-2222-2222-2222-222222222222`

Click **Save**. The bar turns green: **DEMO CONNECTED**.

This is persisted in `localStorage` — you only need to do this once per browser session.

---

## Step 3 — RAG Pipeline (`/console/rag`)

Demonstrates document indexing and grounded Q&A.

1. **Upload a document**
   - Prepare a plain text file (`.txt`, `.md`, `.csv`, or `.json`)
   - Example: save `hello.txt` with content: `Mythos Aegis is a multi-tenant AI SaaS platform.`
   - Click the dashed upload area, select the file, click **Upload**
   - You should see: `Uploaded: hello.txt · N chunks`

2. **List documents**
   - Click **Refresh** in the Documents panel
   - Your uploaded file appears with status `ready`

3. **Ask a question**
   - Type: `What is Mythos Aegis?`
   - Click **Ask**
   - Response includes an answer and citations pointing to your uploaded chunk

**What this proves:** end-to-end document ingestion (chunk → embed via Ollama nomic-embed-text) and retrieval-augmented generation (cosine similarity → Ollama qwen2.5:1.5b → cited answer).

---

## Step 4 — Vision Analysis (`/console/vision`)

Demonstrates image understanding with a vision LLM.

1. Prepare a JPEG or PNG image (any photo works)
2. Click the dashed area, select the image
3. Leave the prompt as-is or type something specific, e.g. `List all text visible in this image`
4. Click **Analyze**
5. Response shows model, provider, and a detailed summary

**What this proves:** binary image upload → Ollama qwen2.5-vl vision inference → structured response (content_type, size metadata — image bytes never logged).

---

## Step 5 — Agent Runtime (`/console/agent`)

Demonstrates multi-step tool-calling.

1. Select an example task or type your own:
   - `List the top 5 most recent audit events`
   - `How many SQL queries were blocked today?`
2. Click **Run Agent**
3. Watch the thinking indicator while the agent loops
4. Response shows:
   - **Answer** — natural language result
   - **Tool calls** — expandable list of each tool invoked, params, success/fail
   - **Iterations** — how many reasoning steps were taken

**What this proves:** LLM agent loop (qwen2.5:1.5b) with structured tool dispatch, up to `AGENT_MAX_ITERATIONS=5` steps.

---

## Step 6 — Billing (`/console/billing`)

Demonstrates the full subscription lifecycle (mock provider, no real money).

1. **View quota** — Shows plan, API request usage, feature flags (RAG, Vision, Workflow), limits
2. **Mock Activate** — Select `pro` from the plan selector, click **Mock Activate**
   - Internally: creates checkout session → activates subscription → refreshes
   - Subscription card updates to show `pro` plan, `active` status
3. **Cancel** — Click **Cancel Subscription**
   - Subscription status updates to `cancelled`
4. **Invoices** — Any invoices generated appear in the list

**What this proves:** the complete billing state machine (free → checkout → activate → cancel) against the mock Stripe provider.

---

## Step 7 — Backend health check (curl)

Verify the API directly:

```bash
# Health — no auth needed
curl http://localhost:8000/health/live
# → {"status": "ok"}

# Plans — public endpoint
curl http://localhost:8000/v1/billing/plans
# → [{"plan": "free", ...}, {"plan": "pro", ...}, ...]

# Authenticated request (replace TOKEN with your JWT)
TOKEN="eyJ..."
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/v1/billing/quota
# → {"plan": "free", "monthly_api_requests": {...}, ...}
```

---

## Step 8 — Intent parser (no auth needed)

```bash
curl -s -X POST http://localhost:8000/intent/parse \
  -H "Content-Type: application/json" \
  -d '{"text": "Cancel my order #1234"}' | python -m json.tool
```

Expected:
```json
{
  "intent": "CANCEL_ORDER",
  "confidence": 0.92,
  "action_type": "WRITE_MUTATION",
  "entities": {},
  "raw_text_hash": "..."
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Admin pages show "Failed to fetch" | CORS not reaching backend | Confirm backend is on port 8000 |
| "Missing token" error | JWT not set in DemoAuthBar | Paste token into amber bar, click Save |
| "Set a Project ID" error | Project ID not set | Paste `22222222-2222-2222-2222-222222222222` |
| RAG upload 503 | Ollama not running or model not pulled | `ollama serve` and `ollama pull nomic-embed-text` |
| Vision 503 | Vision model not pulled | `ollama pull qwen2.5-vl:7b` |
| Agent 503 | Ollama not running | `ollama serve` |
| Token expired | JWT has 24h TTL | Re-run the generation command from step 1 |
| DB connection error | Postgres not running | Start Postgres and run `alembic upgrade head` |

---

## Full demo sequence (15 minutes)

```
 0:00  Start backend + admin console
 1:00  Generate JWT token
 2:00  Paste token + project ID into DemoAuthBar → green
 3:00  RAG: upload hello.txt
 4:00  RAG: click Refresh → see document listed
 5:00  RAG: ask "What is Mythos Aegis?" → see cited answer
 7:00  Vision: upload a photo → see AI analysis
 9:00  Agent: run "List the top 5 most recent audit events"
11:00  Agent: expand tool calls — show reasoning trace
12:00  Billing: mock activate pro plan
13:00  Billing: show quota page (feature flags, limits)
14:00  Billing: cancel subscription
15:00  curl /health/live + /v1/billing/plans — API works headlessly
```
