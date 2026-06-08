# pgvector Installation Guide — Windows PostgreSQL 18

**Status:** pgvector is NOT installed on the current local PostgreSQL 18.1 instance.  
**Impact:** Semantic RAG search works via numpy cosine similarity (correct, but loads all vectors into Python memory). pgvector would enable SQL-side ANN search with an IVFFlat index.  
**Date verified:** 2026-06-08

---

## Current state

| Item | State |
|---|---|
| PostgreSQL | 18.1, service `postgresql-x64-18`, Running |
| pgvector extension | **Not installed** — absent from `pg_available_extensions` |
| Embedding column type | `double precision[]` (FLOAT8 array) |
| Semantic search | Working via numpy cosine similarity in Python |
| Alembic migration `a1b2c3d4e5f6` | Applied as no-op — will fully apply once pgvector is installed |

---

## Why pgvector matters (but isn't blocking now)

The current implementation stores 768-dimensional embeddings as `double precision[]` and
computes cosine similarity in Python via numpy. This is:

- **Functionally correct** — produces the same ranking as pgvector would
- **Verified working** — smoke tested with real Ollama `nomic-embed-text` embeddings (2026-06-08)
- **Adequate for development and small corpora** (< ~10 K chunks)

pgvector adds:
- **SQL-side `<=>` cosine distance operator** — no Python round-trip for every query
- **IVFFlat / HNSW index** — sub-linear approximate nearest-neighbour search at scale
- **Storage efficiency** — `vector(768)` uses 4 bytes/float vs 8 bytes for `double precision[]`

---

## Installation options (choose one)

### Option A — StackBuilder GUI (easiest, no build tools required)

StackBuilder ships with the PostgreSQL installer at:  
`C:\Program Files\PostgreSQL\18\bin\stackbuilder.exe`

Steps:
1. Close all applications that use PostgreSQL.
2. Run StackBuilder (double-click or run from Start Menu).
3. Select **PostgreSQL 18** from the server list.
4. Expand **Add-ons, tools and utilities** → look for **pgvector**.
5. If pgvector appears: select it, click Next, follow the installer.
6. If pgvector does NOT appear for PG18: pgvector is not yet in the StackBuilder
   catalog for this version — use Option B.

After StackBuilder installs pgvector, continue to [Post-install steps](#post-install-steps).

---

### Option B — Build from source with MSVC (requires Visual Studio)

This is the official build path from the pgvector project.

#### Prerequisites

1. **Visual Studio Build Tools** (free, ~4 GB download):
   - Download "Build Tools for Visual Studio" from the Microsoft Visual Studio website
   - During install, select the **"Desktop development with C++"** workload
   - This installs `cl.exe`, `nmake.exe`, and the Windows SDK

2. **Git** — already installed (`C:\Program Files\Git\cmd\git.exe`)

3. PostgreSQL headers — already present at  
   `C:\Program Files\PostgreSQL\18\include\server`

#### Build steps

Run these in a **"x64 Native Tools Command Prompt for VS"** (not standard PowerShell):

```cmd
REM 1. Clone pgvector
git clone https://github.com/pgvector/pgvector.git
cd pgvector

REM 2. Set PostgreSQL path
set "PGROOT=C:\Program Files\PostgreSQL\18"

REM 3. Build
nmake /F Makefile.win

REM 4. Install (copies .dll and .control files to PG directories)
nmake /F Makefile.win install
```

If `nmake /F Makefile.win` is not available, try the CMake path:
```cmd
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
cmake --install build
```

After the build succeeds, continue to [Post-install steps](#post-install-steps).

---

### Option C — Pre-built binary (if available)

The pgvector project publishes pre-built binaries for some Windows/PostgreSQL combinations
on their GitHub Releases page. Check the releases for a `.zip` matching
**pgvector + PostgreSQL 18 + Windows x64**.

If a matching `.zip` is found, extract it and copy:
- `vector.dll` → `C:\Program Files\PostgreSQL\18\lib\`
- `vector.control` → `C:\Program Files\PostgreSQL\18\share\extension\`
- `vector--*.sql` → `C:\Program Files\PostgreSQL\18\share\extension\`

Then restart the PostgreSQL service and continue to [Post-install steps](#post-install-steps).

---

## Post-install steps

Run these after any of the three options above:

### 1. Verify the extension is visible

```powershell
$env:PGPASSWORD = "postgres"
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"
& $psql -U postgres -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';"
```

Expected output:
```
 name  | default_version
-------+-----------------
 vector | 0.8.0
(1 row)
```

If this returns zero rows, the binary files were not copied correctly.

### 2. Roll back and re-apply the migration

The Alembic migration `a1b2c3d4e5f6` was already recorded as a no-op (pgvector was
missing when it first ran). Roll it back and re-apply so it can do the column upgrade:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/mythos_aegis"
& .venv\Scripts\alembic.exe downgrade d7b3e1f4a2c8
& .venv\Scripts\alembic.exe upgrade head
```

Expected migration output:
```
INFO  Running upgrade d7b3e1f4a2c8 -> a1b2c3d4e5f6, Enable pgvector extension and upgrade embedding column.
INFO  pgvector: embedding column upgraded to vector(768)
INFO  pgvector: IVFFlat index created (lists=100)
```

### 3. Verify the column type changed

```powershell
& $psql -U postgres -d mythos_aegis -c "\d document_chunks" 2>&1 | Select-String "embedding"
```

Expected: `embedding | vector(768) | ...` (not `double precision[]`)

### 4. Verify the extension is active

```powershell
& $psql -U postgres -d mythos_aegis -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

### 5. Re-run smoke test

```powershell
$TOKEN = "..." # generate a fresh JWT
& .venv\Scripts\python.exe scripts\_rag_smoke_test.py $TOKEN
```

Upload and search should still work. The search path now uses the `vector` type but the
repository still uses the numpy path — a follow-up sprint can swap to `<=>` SQL operator.

---

## What changes after pgvector is installed

| Item | Before pgvector | After pgvector |
|---|---|---|
| Column type | `double precision[]` (8B/dim) | `vector(768)` (4B/dim) |
| Search path | Python numpy cosine similarity | Still numpy (until search is upgraded) |
| Index | None | IVFFlat cosine ops (lists=100) |
| Storage per 768-dim chunk | ~6.1 KB | ~3.1 KB |
| Search at 10K chunks | Loads all into Python | Still numpy (ANN upgrade is next sprint) |

The IVFFlat index is created but the application still uses the numpy path until
`DocumentChunkRepository.search_similar` is updated to use the `<=>` operator. That is
a one-method change and a separate sprint item.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pg_available_extensions` still empty after install | `.dll` not in `lib/` | Copy `vector.dll` to `C:\Program Files\PostgreSQL\18\lib\` |
| `ERROR: extension "vector" is not available` | Missing `.control` file | Copy `vector.control` + SQL files to `share\extension\` |
| `nmake` not found | VS Build Tools not in PATH | Use "x64 Native Tools Command Prompt for VS" |
| Migration fails on column ALTER | Existing null/wrong-size embedding | Check `WHERE array_length(embedding,1) != 768` before migrating |
| IVFFlat index creation fails | Too few rows for the chosen list count | Reduce `_LISTS` in the migration, or create index after inserting data |
