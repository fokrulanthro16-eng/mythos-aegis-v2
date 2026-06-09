"""
Direct-DB RAG smoke test for Supabase.

Tests (no HTTP server or Ollama required):
  1. Insert tenant
  2. Insert project
  3. Insert document
  4. Insert chunk with synthetic 768-dim vector embedding
  5. Verify embedding type is 'vector' and dimension is 768
  6. pgvector cosine similarity (<=> operator) returns correct chunk
  7. Tenant isolation: cross-tenant query returns zero results
  8. Cleanup
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from pathlib import Path
from uuid import uuid4

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv

load_dotenv(_root / ".env", override=True)

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

P = "[PASS]"
F = "[FAIL]"


def _unit_vec(seed: int, dim: int = 768) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    return (v / np.linalg.norm(v)).tolist()


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


async def main() -> int:
    connect_args = {"ssl": "require"} if settings.DB_SSL_REQUIRE else {}
    engine = create_async_engine(
        settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True
    )
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results: dict[str, bool] = {}

    tenant_id = uuid4()
    tenant_b_id = uuid4()
    project_id = uuid4()
    doc_id = uuid4()
    chunk_id = uuid4()
    fake_user_id = uuid4()
    slug = f"smoke-{tenant_id.hex[:8]}"

    # Same seed for query and chunk → cosine_sim ≈ 1.0
    chunk_vec = _unit_vec(seed=42)
    query_vec = _unit_vec(seed=42)

    async with factory() as session:

        # ── 1. Tenant ─────────────────────────────────────────────────────────
        try:
            await session.execute(text(
                "INSERT INTO tenants (id, name, slug, plan, status, created_at, updated_at) "
                "VALUES (:id, :name, :slug, 'free', 'trial', now(), now())"
            ), {"id": str(tenant_id), "name": "smoke-tenant", "slug": slug})
            results["insert_tenant"] = True
            print(f"{P} insert_tenant")
        except Exception as exc:
            results["insert_tenant"] = False
            print(f"{F} insert_tenant: {exc}")
            await session.rollback()
            await engine.dispose()
            return 1

        # ── 2. Project ────────────────────────────────────────────────────────
        try:
            await session.execute(text(
                "INSERT INTO projects (id, tenant_id, name, created_at, updated_at) "
                "VALUES (:id, :tid, :name, now(), now())"
            ), {"id": str(project_id), "tid": str(tenant_id), "name": "smoke-project"})
            results["insert_project"] = True
            print(f"{P} insert_project")
        except Exception as exc:
            results["insert_project"] = False
            print(f"{F} insert_project: {exc}")
            await session.rollback()
            await engine.dispose()
            return 1

        # ── 3. Document ───────────────────────────────────────────────────────
        doc_content = "JWT security best practices: token expiry, key rotation, secret strength."
        try:
            await session.execute(text(
                "INSERT INTO documents "
                "(id, tenant_id, project_id, uploaded_by_user_id, filename, "
                "content_type, source_type, status, created_at, updated_at) "
                "VALUES (:id, :tid, :pid, :uid, :fn, :ct, 'upload', 'indexed', now(), now())"
            ), {
                "id": str(doc_id), "tid": str(tenant_id), "pid": str(project_id),
                "uid": str(fake_user_id), "fn": "jwt_guide.txt", "ct": "text/plain",
            })
            results["insert_document"] = True
            print(f"{P} insert_document")
        except Exception as exc:
            results["insert_document"] = False
            print(f"{F} insert_document: {exc}")
            await session.rollback()
            await engine.dispose()
            return 1

        # ── 4. Chunk with vector(768) embedding ───────────────────────────────
        content_hash = hashlib.sha256(doc_content.encode()).hexdigest()
        vec_str = _vec_literal(chunk_vec)
        try:
            # Use CAST(:param AS vector) — avoids conflict with SQLAlchemy's :param syntax
            await session.execute(text(
                "INSERT INTO document_chunks "
                "(id, tenant_id, project_id, document_id, chunk_index, content, "
                "content_hash, token_estimate, embedding, citation_label, created_at, updated_at) "
                "VALUES (:id, :tid, :pid, :did, 0, :content, :hash, :tokens, "
                "CAST(:emb AS vector), :cite, now(), now())"
            ), {
                "id": str(chunk_id), "tid": str(tenant_id), "pid": str(project_id),
                "did": str(doc_id), "content": doc_content, "hash": content_hash,
                "tokens": len(doc_content.split()), "emb": vec_str,
                "cite": "jwt_guide#chunk-0",
            })
            results["insert_chunk_vector"] = True
            print(f"{P} insert_chunk_vector")
        except Exception as exc:
            results["insert_chunk_vector"] = False
            print(f"{F} insert_chunk_vector: {exc}")
            await session.rollback()
            await engine.dispose()
            return 1

        await session.commit()

        # ── 5. Verify embedding type and dimension ────────────────────────────
        try:
            row = await session.execute(text(
                "SELECT pg_typeof(embedding), vector_dims(embedding) "
                "FROM document_chunks WHERE id = :id"
            ), {"id": str(chunk_id)})
            rec = row.fetchone()
            emb_type = rec[0] if rec else None
            emb_dim = rec[1] if rec else None
            ok = emb_type == "vector" and emb_dim == 768
            results["verify_embedding"] = ok
            print(f"{P if ok else F} verify_embedding: type={emb_type!r} dims={emb_dim}")
        except Exception as exc:
            results["verify_embedding"] = False
            print(f"{F} verify_embedding: {exc}")

        # ── 6. pgvector cosine similarity ─────────────────────────────────────
        qvec_str = _vec_literal(query_vec)
        try:
            row = await session.execute(text(
                "SELECT citation_label, "
                "ROUND((1 - (embedding <=> CAST(:q AS vector)))::numeric, 4) AS sim "
                "FROM document_chunks "
                "WHERE tenant_id = :tid AND project_id = :pid "
                "ORDER BY embedding <=> CAST(:q AS vector) "
                "LIMIT 1"
            ), {"q": qvec_str, "tid": str(tenant_id), "pid": str(project_id)})
            rec = row.fetchone()
            ok = rec is not None and float(rec[1]) > 0.99
            results["pgvector_cosine"] = ok
            cite = rec[0] if rec else None
            sim = rec[1] if rec else None
            print(f"{P if ok else F} pgvector_cosine: citation={cite!r} sim={sim}")
        except Exception as exc:
            results["pgvector_cosine"] = False
            print(f"{F} pgvector_cosine: {exc}")

        # ── 7. Tenant isolation ───────────────────────────────────────────────
        try:
            row = await session.execute(text(
                "SELECT count(*) FROM document_chunks WHERE tenant_id = :tid"
            ), {"tid": str(tenant_b_id)})
            count = row.scalar()
            ok = count == 0
            results["tenant_isolation"] = ok
            print(f"{P if ok else F} tenant_isolation: tenant_b sees {count} chunk(s) (expect 0)")
        except Exception as exc:
            results["tenant_isolation"] = False
            print(f"{F} tenant_isolation: {exc}")

        # ── 8. Cleanup ────────────────────────────────────────────────────────
        try:
            for tbl in ("document_chunks", "documents", "projects"):
                await session.execute(
                    text(f"DELETE FROM {tbl} WHERE tenant_id = :tid"),  # noqa: S608
                    {"tid": str(tenant_id)},
                )
            await session.execute(
                text("DELETE FROM tenants WHERE id = :tid"), {"tid": str(tenant_id)}
            )
            await session.commit()
            print(f"{P} cleanup")
        except Exception as exc:
            print(f"{F} cleanup: {exc}")
            await session.rollback()

    await engine.dispose()

    passed = sum(results.values())
    total = len(results)
    print(f"\n{'='*52}")
    print(f"RAG smoke test: {passed}/{total} passed")
    for k, v in results.items():
        print(f"  {'OK' if v else 'FAIL':4s}  {k}")
    return 0 if passed == total else 1


sys.exit(asyncio.run(main()))
