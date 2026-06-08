# Supabase Setup Guide — Mythos Aegis

Connect the backend to Supabase PostgreSQL with pgvector in four steps.

---

## Prerequisites

- A Supabase account (free tier works)
- Python virtual environment activated (`.\venv\Scripts\Activate.ps1` on Windows)
- Alembic installed (`pip install alembic` or already in `requirements.txt`)

---

## Step 1: Create a Supabase Project

1. Log in at <https://supabase.com/dashboard>
2. Click **New project**
3. Choose an organization, set a strong **database password**, pick the nearest region
4. Wait ~2 minutes for provisioning

---

## Step 2: Enable pgvector

Supabase ships pgvector pre-installed but the extension must be enabled per-database.

1. Open your project → **SQL Editor**
2. Run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

Expected output: one row with `vector` and a version string (≥0.5.0).

---

## Step 3: Get the Connection String

1. Go to **Settings → Database**
2. Under **Connection string**, select **URI** and copy the **Direct connection** string
   (not the transaction pooler — Alembic migrations require a direct connection)
3. The URL looks like:

```
postgresql://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres
```

4. Replace the driver prefix for asyncpg:

```
postgresql+asyncpg://postgres.[ref]:[PASSWORD]@aws-0-[region].pooler.supabase.com:5432/postgres
```

> **Note:** Use the **direct** port 5432, not the pooler port 6543.
> Migrations use DDL transactions that are incompatible with PgBouncer transaction-mode pooling.

---

## Step 4: Configure `.env`

Add or replace the database block in your `.env`:

```dotenv
# ── Supabase ──────────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[PASSWORD]@db.[ref].supabase.co:5432/postgres
DB_SSL_REQUIRE=true
USE_PGVECTOR=true
```

> `DB_SSL_REQUIRE=true` tells both the app engine and Alembic to pass `ssl="require"` to asyncpg.
> `USE_PGVECTOR=true` switches the `DocumentChunk.embedding` column type from `ARRAY(Float)` to `Vector(768)`.

---

## Step 5: Run Migrations

```powershell
# In the project root, with .env loaded
.\.venv\Scripts\Activate.ps1

# Apply all migrations including a1b2c3d4e5f6 (pgvector column + index)
alembic upgrade head
```

Expected final line: `INFO  [alembic.runtime.migration] Running upgrade d7b3e1f4a2c8 -> a1b2c3d4e5f6, Enable pgvector extension and migrate embedding column`

The migration will:
- Run `CREATE EXTENSION IF NOT EXISTS vector`
- `ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768)`
- Create an IVFFlat index (`ix_chunk_embedding_ivfflat`)

Verify in the SQL Editor:

```sql
\d document_chunks
-- embedding column should show: vector(768)

SELECT indexname FROM pg_indexes WHERE tablename = 'document_chunks';
-- should include ix_chunk_embedding_ivfflat
```

---

## Step 6: Start the Backend

```powershell
uvicorn app.main:app --reload
```

Health check: `GET /api/v1/health/ready` → `{"status": "ready"}`

---

## Step 7: Validate RAG Upload and Search

Generate a JWT first (replace the dev secret with yours if changed):

```powershell
python scripts/generate_dev_token.py
```

Then run the smoke test:

```powershell
python scripts/_rag_smoke_test.py <TOKEN>
```

Expected output:

```
Upload status: indexed  chunks: 1
--- Query 1 ---
jwt_security_guide#chunk-0  score=0.xx
--- Query 2 ---
jwt_security_guide#chunk-0  score=0.xx
```

---

## Step 8: Verify pgvector Search (optional SQL check)

In the Supabase SQL Editor, after uploading at least one document:

```sql
-- Confirm vector type
SELECT pg_typeof(embedding) FROM document_chunks LIMIT 1;
-- Expected: vector

-- Confirm IVFFlat index exists
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'document_chunks'
  AND indexname = 'ix_chunk_embedding_ivfflat';
```

---

## Environment Variable Reference

| Variable | Local dev | Supabase |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/mythos_aegis` | `postgresql+asyncpg://postgres.[ref]:[PW]@db.[ref].supabase.co:5432/postgres` |
| `DB_SSL_REQUIRE` | `false` | `true` |
| `USE_PGVECTOR` | `false` (pgvector not installed locally) | `true` |

---

## Troubleshooting

**`asyncpg.exceptions.InvalidAuthorizationSpecificationError`**  
Wrong password. Double-check the password in the Supabase dashboard (Settings → Database → Reset database password if needed).

**`SSL SYSCALL error: EOF detected`**  
Missing `DB_SSL_REQUIRE=true`. Supabase requires TLS.

**`type "vector" does not exist`** during migration  
Run `CREATE EXTENSION IF NOT EXISTS vector;` in the SQL Editor first (Step 2), then re-run `alembic upgrade head`.

**`connection refused` on port 5432**  
Use the **direct** connection string from Settings → Database, not the pooler URL (pooler uses port 6543).

**Migration `a1b2c3d4e5f6` already applied but column is still `double precision[]`**  
The migration ran as a no-op on local PG18 (no pgvector). On Supabase it will run fully. If you applied it locally first, you may need to stamp:

```powershell
alembic downgrade d7b3e1f4a2c8
alembic upgrade head
```
