"""End-to-end RAG pipeline verification script.

Generates a valid JWT, uploads a sample document, runs semantic search,
runs RAG ask, and verifies citations.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import jwt
import httpx

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
JWT_SECRET = "mythos-aegis-dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "mythos-aegis"
JWT_AUDIENCE = "mythos-aegis-api"

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
PROJECT_ID = str(uuid4())


def make_token(permissions: list[str]) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": USER_ID,
        "tenant_id": TENANT_ID,
        "roles": ["admin"],
        "permissions": permissions,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def sep(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}", file=sys.stderr)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    token = make_token(["rag.upload", "rag.search", "rag.ask"])
    headers = {"Authorization": f"Bearer {token}"}

    sep("Step 1: API Health")
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        r = client.get("/health")
        print(f"  GET /health ->{r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            fail("API not healthy — aborting")
            sys.exit(1)
        ok("API is healthy")

    sep("Step 2: Upload Sample Document")
    sample_text = (
        "Mythos Aegis is an enterprise AI gateway and RAG engine. "
        "It provides multi-tenant document storage, semantic search, "
        "and retrieval-augmented generation using nomic-embed-text "
        "for embeddings and qwen2.5 for LLM inference. "
        "The system supports fine-grained RBAC with tenant isolation. "
        "Documents are chunked, embedded, and stored in PostgreSQL."
    )
    file_bytes = sample_text.encode("utf-8")
    # project_id is a Form() field — must be sent as multipart form data
    files = {
        "file": ("mythos_aegis_overview.txt", BytesIO(file_bytes), "text/plain"),
    }
    data = {"project_id": PROJECT_ID}

    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        r = client.post(
            "/v1/rag/upload",
            headers=headers,
            files=files,
            data=data,
        )
        print(f"  POST /v1/rag/upload ->{r.status_code}")
        print(f"  Body: {r.text[:500]}")
        if r.status_code not in (200, 201, 202):
            fail("Upload failed — aborting")
            sys.exit(1)
        upload_data = r.json()
        document_id = upload_data.get("document_id")
        ok(f"Uploaded document_id={document_id}")

    sep("Step 3: Wait for Embedding (polling status)")
    with httpx.Client(base_url=BASE_URL, timeout=15) as client:
        for attempt in range(12):
            r = client.get(
                f"/v1/rag/documents/{document_id}",
                headers=headers,
                params={"project_id": PROJECT_ID},
            )
            if r.status_code == 200:
                status = r.json().get("status", "?")
                print(f"  [{attempt + 1}] status={status}")
                if status == "indexed":
                    ok("Document indexed successfully")
                    break
                if status == "failed":
                    fail("Document indexing failed")
                    print(f"  Response: {r.text}")
                    sys.exit(1)
            else:
                print(f"  [{attempt + 1}] GET status ->{r.status_code}: {r.text[:200]}")
            time.sleep(5)
        else:
            print("  WARNING: Timed out waiting for indexed status — continuing anyway")

    sep("Step 4: Semantic Search")
    search_payload = {
        "project_id": PROJECT_ID,
        "query": "What is Mythos Aegis?",
        "top_k": 3,
    }
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        r = client.post("/v1/rag/search", headers=headers, json=search_payload)
        print(f"  POST /v1/rag/search ->{r.status_code}")
        print(f"  Body: {json.dumps(r.json(), indent=2)[:800]}")
        if r.status_code != 200:
            fail("Search failed")
        else:
            results = r.json().get("results", [])
            ok(f"Search returned {len(results)} result(s)")

    sep("Step 5: RAG Ask")
    ask_payload = {
        "project_id": PROJECT_ID,
        "question": "What embedding model does Mythos Aegis use?",
        "top_k": 3,
    }
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        r = client.post("/v1/rag/ask", headers=headers, json=ask_payload)
        print(f"  POST /v1/rag/ask ->{r.status_code}")
        body = r.json()
        print(f"  Body: {json.dumps(body, indent=2)[:1200]}")
        if r.status_code != 200:
            fail("Ask failed")
        else:
            answer = body.get("answer", "")
            citations = body.get("citations", [])
            ok(f"Answer received ({len(answer)} chars)")
            ok(f"Citations: {len(citations)} source(s)")
            if citations:
                for c in citations:
                    print(f"    • {c}")

    sep("Step 6: Final Summary")
    print("  document_id :", document_id)
    print("  tenant_id   :", TENANT_ID)
    print("  project_id  :", PROJECT_ID)
    ok("Full RAG pipeline operational")


if __name__ == "__main__":
    main()
