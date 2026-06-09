"""Verify Supabase connection, alembic state, pgvector, tables, and vector column."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main() -> None:
    connect_args = {"ssl": "require"} if settings.DB_SSL_REQUIRE else {}
    engine = create_async_engine(settings.DATABASE_URL, connect_args=connect_args)

    async with engine.connect() as conn:
        # alembic version (table may not exist on fresh DB)
        try:
            rows = await conn.execute(
                text("SELECT version_num FROM alembic_version ORDER BY 1")
            )
            versions = [r[0] for r in rows]
            print(f"[alembic] applied revisions: {versions}")
        except Exception as exc:
            print(f"[alembic] ERROR reading alembic_version: {exc}")

        # table list
        rows = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' ORDER BY tablename"
            )
        )
        tables = [r[0] for r in rows]
        print(f"[tables] count={len(tables)}: {tables}")

        # pgvector extension
        rows = await conn.execute(
            text("SELECT extname, extversion FROM pg_extension WHERE extname='vector'")
        )
        vec = rows.fetchall()
        print(f"[pgvector] extension present: {bool(vec)}  {vec}")

        # embedding column type on document_chunks
        rows = await conn.execute(
            text(
                "SELECT column_name, udt_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_name='document_chunks' AND column_name='embedding'"
            )
        )
        col = rows.fetchall()
        print(f"[embedding column] {col}")

        # IVFFlat index
        rows = await conn.execute(
            text(
                "SELECT indexname, indexdef "
                "FROM pg_indexes "
                "WHERE tablename='document_chunks' "
                "AND indexname='ix_chunk_embedding_ivfflat'"
            )
        )
        idx = rows.fetchall()
        print(f"[IVFFlat index] present: {bool(idx)}")
        if idx:
            print(f"  {idx[0][1]}")

    await engine.dispose()
    print("[done]")


asyncio.run(main())
