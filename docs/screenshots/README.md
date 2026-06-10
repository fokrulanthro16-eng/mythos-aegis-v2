# Screenshots — Mythos Aegis v0.5.0-demo

Evidence package for mentor submission.  
Add each PNG to this folder, then commit with `git add docs/screenshots/ && git commit -m "docs: add project screenshots"`.

---

## Required screenshots

| File | What to capture |
|---|---|
| `github-repo-homepage.png` | The GitHub repo landing page showing repo name, description, language, and recent commit |
| `github-actions-green.png` | GitHub → Actions tab showing the most recent CI run (`ci.yml`) with a green checkmark |
| `supabase-pgvector-setup.png` | Supabase SQL Editor showing `SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';` with a result row |
| `health-endpoint.png` | Browser or terminal showing `GET /health` → `{"status":"ok"}` and `GET /status` → full JSON response |
| `status-endpoint.png` | Terminal showing `curl http://localhost:8000/status` with `service`, `version`, `database`, `redis` fields visible |
| `rag-query-result.png` | Admin console `/console/rag` — a question answered with cited chunks visible in the response |
| `gemini-vision-result.png` | Terminal or browser showing `POST /vision/analyze` response with `summary`, `detected_objects`, and `observations` fields |
| `test-summary.png` | Terminal showing `pytest -q` final line: `961 passed, 0 failures` |

---

## Capture instructions

### `github-repo-homepage.png`
1. Open `https://github.com/fokrulanthro16-eng/mythos-aegis-v2`
2. Ensure the repo description and `main` branch are visible
3. Screenshot the full page above the fold

### `github-actions-green.png`
1. Open the repo → **Actions** tab
2. Click the most recent workflow run for `ci.yml`
3. Screenshot showing the green ✅ and the job names (lint, type-check, test)

### `supabase-pgvector-setup.png`
1. Open your Supabase project → **SQL Editor**
2. Run:
   ```sql
   SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
   ```
3. Screenshot the result row showing `vector` and a version string

### `health-endpoint.png`
1. With backend running on port 8000, run:
   ```powershell
   curl http://localhost:8000/health
   curl http://localhost:8000/status
   ```
2. Screenshot the terminal showing both responses

### `status-endpoint.png`
1. Run `curl http://localhost:8000/status`
2. Screenshot showing all four fields: `service`, `version`, `database`, `redis`

### `rag-query-result.png`
1. Open `http://localhost:3001/console/rag`
2. Ensure DemoAuthBar is green (JWT + project ID set)
3. Upload a document, then ask a question
4. Screenshot the response panel showing the answer and at least one citation

### `gemini-vision-result.png`
1. Ensure `GEMINI_API_KEY` is set in `.env`
2. Run:
   ```powershell
   curl -X POST http://localhost:8000/vision/analyze `
     -H "Authorization: Bearer $TOKEN" `
     -F "file=@photo.jpg"
   ```
3. Screenshot the terminal showing the JSON response with `summary`, `detected_objects`, `observations`

### `test-summary.png`
1. From the repo root with venv active, run:
   ```powershell
   python -m pytest -q
   ```
2. Wait for completion (~2 minutes)
3. Screenshot the final summary line: `961 passed, 0 failures, 8 warnings`

---

## After adding all screenshots

```powershell
git add docs/screenshots/
git commit -m "docs: add project screenshots"
git push origin main
```
