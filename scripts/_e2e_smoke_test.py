"""
End-to-end RAG smoke test.

Pipeline:
  1. Generate a dev JWT with rag.upload / rag.search / rag.ask permissions
  2. Start uvicorn on port 8001
  3. Wait for /health/ready
  4. Upload test document → Ollama embeds → Supabase stores vector(768)
  5. Semantic search via pgvector <=> operator
  6. Verify document + chunk exist in Supabase
  7. Stop uvicorn
  8. Print pass/fail report
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(_root / ".env", override=True)

import jwt
import requests
from app.core.config import settings

P = "[PASS]"
F = "[FAIL]"

PROJECT_ID = "30000000-0000-0000-0000-000000000001"
BASE = "http://localhost:8001"

DOC = (
    "JWT Authentication Security Guidelines\n\n"
    "JSON Web Tokens (JWT) are used to securely transmit claims between parties.\n"
    "Key security principles:\n"
    "1. Always verify the signature before inspecting payload claims.\n"
    "2. Validate the issuer (iss) and audience (aud) to prevent token reuse.\n"
    "3. Use a strong randomly-generated secret key of at least 32 bytes for HS256.\n"
    "4. Set short expiry times and implement refresh token rotation.\n"
    "5. Never log the raw JWT token string.\n"
    "Token revocation: use short-lived tokens and a block-list for emergency revocation.\n"
)


def make_token() -> str:
    now = int(time.time())
    tenant_id = str(uuid4())
    payload = {
        "sub": str(uuid4()),
        "tenant_id": tenant_id,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "permissions": ["rag.upload", "rag.search", "rag.ask"],
        "roles": ["user"],
        "iat": now,
        "exp": now + 7200,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def wait_ready(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(f"{BASE}/health/ready", timeout=2)
            if r.status == 200:
                return True
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    results: dict[str, bool] = {}
    token = make_token()
    headers = {"Authorization": f"Bearer {token}"}

    # ── Start uvicorn ─────────────────────────────────────────────────────────
    print("Starting uvicorn on port 8001 …")
    env = {**os.environ, "PORT": "8001"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8001", "--log-level", "warning"],
        cwd=str(_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    ready = wait_ready(timeout=30)
    results["server_ready"] = ready
    if not ready:
        print(f"{F} server_ready: uvicorn did not become ready within 30s")
        if proc.stderr:
            import select as _sel
            # Non-blocking drain — avoid blocking on empty stderr pipe
            try:
                ready_fds = _sel.select([proc.stderr], [], [], 0.5)[0]
                stderr_out = proc.stderr.read(2000) if ready_fds else b"(no stderr output)"
            except Exception:
                stderr_out = b"(stderr unreadable)"
        else:
            stderr_out = b""
        print("  stderr:", stderr_out.decode(errors="replace")[:500])
        proc.terminate()
        return 1
    print(f"{P} server_ready")

    try:
        # ── Health check ──────────────────────────────────────────────────────
        r = requests.get(f"{BASE}/health/ready", timeout=5)
        ok = r.status_code == 200 and r.json().get("status") == "ready"
        results["health_ready"] = ok
        print(f"{P if ok else F} health_ready: {r.json()}")

        # ── RAG upload ────────────────────────────────────────────────────────
        print("Uploading document (Ollama will embed) …")
        r = requests.post(
            f"{BASE}/v1/rag/upload",
            headers=headers,
            files={"file": ("jwt_security_guide.txt", io.BytesIO(DOC.encode()), "text/plain")},
            data={"project_id": PROJECT_ID},
            timeout=120,
        )
        ok = r.status_code == 200
        results["rag_upload"] = ok
        if ok:
            body = r.json()
            doc_id = body.get("document_id")
            chunks = body.get("chunk_count", 0)
            print(f"{P} rag_upload: doc_id={doc_id} chunks={chunks}")
        else:
            print(f"{F} rag_upload: status={r.status_code} body={r.text[:200]}")
            return 1

        # ── Semantic search ───────────────────────────────────────────────────
        queries = [
            "How should I handle token expiry and secret key strength?",
            "What are best practices for secure authentication tokens?",
        ]
        for q in queries:
            r2 = requests.post(
                f"{BASE}/v1/rag/search",
                headers={**headers, "Content-Type": "application/json"},
                json={"query": q, "project_id": PROJECT_ID, "top_k": 3},
                timeout=60,
            )
            ok = r2.status_code == 200 and len(r2.json().get("results", [])) > 0
            key = f"rag_search:{q[:30]}"
            results[key] = ok
            if ok:
                top = r2.json()["results"][0]
                print(f"{P} rag_search: citation={top['citation_label']!r} (query={q[:40]!r})")
            else:
                print(f"{F} rag_search: status={r2.status_code} body={r2.text[:200]}")

        # ── Verify chunk in DB has vector type ────────────────────────────────
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        connect_args = {"ssl": "require"} if settings.DB_SSL_REQUIRE else {}
        engine = create_async_engine(settings.DATABASE_URL, connect_args=connect_args)
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def verify_db() -> bool:
            async with factory() as session:
                row = await session.execute(text(
                    "SELECT pg_typeof(embedding), vector_dims(embedding) "
                    "FROM document_chunks "
                    "WHERE document_id = :did LIMIT 1"
                ), {"did": doc_id})
                rec = row.fetchone()
                await engine.dispose()
                return rec is not None and rec[0] == "vector" and rec[1] == 768

        db_ok = asyncio.run(verify_db())
        results["db_vector_verified"] = db_ok
        print(f"{P if db_ok else F} db_vector_verified: pgvector column confirmed in Supabase")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    passed = sum(results.values())
    total = len(results)
    print(f"\n{'='*56}")
    print(f"E2E smoke test: {passed}/{total} passed")
    for k, v in results.items():
        print(f"  {'OK' if v else 'FAIL':4s}  {k}")
    return 0 if passed == total else 1


sys.exit(main())
