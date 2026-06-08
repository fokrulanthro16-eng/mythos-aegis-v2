"""RAG pipeline smoke test — upload, verify, search, check embedding."""
from __future__ import annotations

import io
import json
import sys

import requests

TOKEN = sys.argv[1] if len(sys.argv) > 1 else ""
PROJECT = "30000000-0000-0000-0000-000000000001"
BASE = "http://localhost:8001"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ---------------------------------------------------------------------------
# 1. Upload — substantive content so semantic search can distinguish it
# ---------------------------------------------------------------------------
DOC = (
    "JWT Authentication Security Guidelines\n\n"
    "JSON Web Tokens (JWT) are used to securely transmit claims between parties.\n\n"
    "Key security principles:\n"
    "1. Always verify the signature before inspecting payload claims.\n"
    "2. Validate the issuer (iss) and audience (aud) to prevent token reuse.\n"
    "3. Use a strong randomly-generated secret key of at least 32 bytes for HS256.\n"
    "4. Set short expiry times and implement refresh token rotation.\n"
    "5. Never log the raw JWT token string — only log tenant_id from verified claims.\n"
    "6. Implement zero-downtime key rotation with a previous-key fallback.\n\n"
    "Token revocation: JWTs are stateless. Use short-lived tokens and a block-list "
    "for emergency revocation.\n"
)

print("=== STEP 1: Upload document ===")
r = requests.post(
    f"{BASE}/v1/rag/upload",
    headers=HEADERS,
    files={"file": ("jwt_security_guide.txt", io.BytesIO(DOC.encode()), "text/plain")},
    data={"project_id": PROJECT},
    timeout=60,
)
print(f"STATUS: {r.status_code}")
body = r.json()
print(f"BODY:   {json.dumps(body, indent=2)}")

if r.status_code != 200:
    print("FAIL: upload did not return 200")
    sys.exit(1)

doc_id = body["document_id"]
chunk_count = body.get("chunk_count", 0)
print(f"\ndoc_id={doc_id}  chunk_count={chunk_count}")

# ---------------------------------------------------------------------------
# 2. Semantic search — related query (not verbatim match)
# ---------------------------------------------------------------------------
print("\n=== STEP 2: Semantic search (related, not verbatim) ===")
search_queries = [
    "How should I handle token expiry and secret key strength?",
    "What are best practices for secure authentication tokens?",
]

for query in search_queries:
    r2 = requests.post(
        f"{BASE}/v1/rag/search",
        headers={**HEADERS, "Content-Type": "application/json"},
        json={"query": query, "project_id": PROJECT, "top_k": 3},
        timeout=60,
    )
    print(f"\nQuery: {query!r}")
    print(f"STATUS: {r2.status_code}")
    if r2.status_code == 200:
        data = r2.json()
        results = data.get("results", [])
        print(f"Results: {len(results)} chunk(s) returned")
        for i, res in enumerate(results):
            print(f"  [{i}] citation={res['citation_label']}  excerpt={res['excerpt'][:80]!r}")
    else:
        print(f"BODY: {r2.text[:300]}")

print("\n=== DONE ===")
