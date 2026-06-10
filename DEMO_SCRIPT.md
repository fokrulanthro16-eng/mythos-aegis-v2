# Mythos Aegis — 3-Minute Demo Script

> Read-aloud guide for a mentor review session.
> Total time: ~3 minutes. Pause briefly at each section break.

---

## 0:00 – 0:20 | Introduction

> *Say this while the repo or README is visible on screen.*

"This is Mythos Aegis — an AI security and RAG demo platform.
It's a production-style FastAPI backend paired with a Next.js admin console.
The core features are JWT authentication with RBAC, an SQL Airlock for query safety,
a full RAG pipeline backed by Supabase pgvector, and a Vision analyzer that works
completely offline through a built-in fallback provider."

---

## 0:20 – 0:50 | Architecture

> *Show the Architecture section of README or the admin dashboard homepage.*

"The backend is FastAPI with async SQLAlchemy and asyncpg.
The admin console is Next.js 15 running at localhost:3001.
The database is Postgres — Supabase in the cloud setup, with the pgvector extension
enabled for 768-dimensional semantic embeddings.

The Vision system is pluggable: you can point it at Ollama locally, Gemini in the cloud,
or leave it in fallback mode for offline demos — which is how it's configured right now."

---

## 0:50 – 1:25 | Auth, RBAC, and SQL Airlock

> *Show the /health and /status responses, then the security section of the admin console.*

"Let me show the health and status endpoints first.
GET /health returns status ok. GET /status shows service name, version,
database connectivity, and Redis state — useful for ops and readiness probes.

Authentication is JWT HS256. Every request carries a Bearer token.
The middleware validates all claims — issuer, audience, expiry — before the request
reaches any handler. Raw tokens are never logged.

Permissions are checked per endpoint. Uploading a document requires `rag.upload`.
Analyzing an image requires `vision.analyze`. No permission, no access — 403.

The SQL Airlock sits in front of any natural-language-to-SQL path.
Queries go through three stages: fingerprint check, intent classification,
and injection guard. Anything that fails is rejected and logged."

---

## 1:25 – 2:10 | RAG Upload and Ask with Citations

> *Show the /console/rag page with a document uploaded and a question answered.*

"Here's the RAG pipeline in action.

I upload a PDF through the admin console. The backend extracts the text,
splits it into chunks, embeds each chunk using nomic-embed-text via Ollama,
and stores the 768-dimensional vectors in Supabase with pgvector.

Now I ask a question. The backend embeds the question the same way,
runs a cosine-distance search against the stored chunks — that's the `<=>` operator
in pgvector — retrieves the top-K results, and passes them to the LLM as grounded context.

The response comes back with the answer and the source citations.
You can see exactly which chunks the answer was drawn from.
That's the screenshot in the README — rag-query-result.png."

---

## 2:10 – 2:35 | Vision Analyze — Fallback Mode

> *Show the /console/vision page or the vision-analyze-fallback.png screenshot.*

"The Vision analyzer accepts JPEG, PNG, WebP, GIF, and PDF files.

For this demo, the provider is set to fallback mode — VISION_PROVIDER=fallback in .env.
That means no Ollama vision model and no Gemini API key are required.
The fallback provider returns a structured JSON response with a summary,
detected objects list, and observations list — immediately, with no network call.

When a real key is available, switching to Gemini is a single env var change.
The factory function reads VISION_PROVIDER at startup and routes accordingly."

---

## 2:35 – 3:00 | Test Evidence and Close

> *Show the Test Evidence section of the README or a terminal running pytest.*

"On the quality side:

Ruff passes with zero lint errors.
Mypy passes with zero type errors.
Pytest runs 980-plus tests with zero failures and coverage above 90 percent.
All three GitHub Actions workflows — CI, Docker build, and security scan — are green on main.

The working tree is clean, main is synced with origin, and there are no outstanding
WARN or FAIL items from the release review.

Mythos Aegis is demo-ready and ready for mentor review. Thank you."

---

> **Tip:** If a live service isn't running, the screenshots in `docs/screenshots/`
> cover every key moment in this script. Fallback to screenshots is seamless.
