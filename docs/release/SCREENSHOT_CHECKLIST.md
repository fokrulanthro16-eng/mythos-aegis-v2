# Screenshot Checklist — Mythos Aegis v0.4.0

Capture these screenshots with a live stack (Postgres + Ollama + backend + admin) and save
to `docs/screenshots/`.

---

## Pre-flight

- [ ] Backend running on `http://localhost:8000`
- [ ] Admin console running on `http://localhost:3001`
- [ ] Demo JWT generated and pasted into DemoAuthBar
- [ ] Project ID `22222222-2222-2222-2222-222222222222` set in DemoAuthBar
- [ ] DemoAuthBar shows green **DEMO CONNECTED** state

---

## Admin Console pages

### 1. Command Center — `/console`
- [ ] `01-dashboard.png` — Dashboard loaded with metric cards visible (requests, error rate, latency, tenants)
- [ ] `02-dashboard-risk-gauge.png` — Risk gauge rendered with score displayed

### 2. RAG Pipeline — `/console/rag`
- [ ] `03-rag-upload-before.png` — Upload area in idle state (dashed dropzone)
- [ ] `04-rag-upload-success.png` — Upload success banner: `Uploaded: hello.txt · N chunks`
- [ ] `05-rag-documents-list.png` — Documents panel showing `hello.txt` with status `ready`
- [ ] `06-rag-ask-answer.png` — Ask "What is Mythos Aegis?" with answer and citations visible

### 3. Vision Analysis — `/console/vision`
- [ ] `07-vision-idle.png` — Upload area in idle state
- [ ] `08-vision-result.png` — Vision analysis result showing model, provider, and description

### 4. Agent Runner — `/console/agent`
- [ ] `09-agent-idle.png` — Task input and Run button, no results yet
- [ ] `10-agent-result.png` — Agent result with answer, tool calls expanded, iterations shown

### 5. Billing — `/console/billing`
- [ ] `11-billing-free.png` — Free plan, quota widget, feature flags
- [ ] `12-billing-activate.png` — Plan selector showing `pro` selected before activation
- [ ] `13-billing-pro-active.png` — Subscription card showing `pro` / `active` after activation
- [ ] `14-billing-cancelled.png` — Subscription showing `cancelled` status after cancel

### 6. Tenants — `/console/tenants`
- [ ] `15-tenants.png` — Tenant list (may be empty on fresh DB, that is fine)

### 7. Observability — `/console/observability`
- [ ] `16-observability.png` — Health status and metrics panel

### 8. Security Events — `/console/security`
- [ ] `17-security.png` — Security events list (may be empty on fresh DB)

### 9. SQL Airlock — `/console/airlock`
- [ ] `18-airlock.png` — Airlock decisions list

### 10. Settings — `/console/settings`
- [ ] `19-settings.png` — Settings page

---

## API / CLI

- [ ] `20-health-curl.png` — Terminal: `curl http://localhost:8000/health/live` → `{"status":"ok"}`
- [ ] `21-intent-parse-curl.png` — Terminal: `POST /intent/parse` with JSON response
- [ ] `22-billing-plans-curl.png` — Terminal: `curl http://localhost:8000/v1/billing/plans`

---

## DemoAuthBar states

- [ ] `23-demoauthbar-amber.png` — Amber state: **DEMO SETUP REQUIRED**
- [ ] `24-demoauthbar-green.png` — Green state: **DEMO CONNECTED**

---

## Notes

- Use browser zoom 100% (default) for all screenshots
- Window width ≥ 1280 px recommended
- Clear browser localStorage before the amber-bar screenshots to capture the setup flow
