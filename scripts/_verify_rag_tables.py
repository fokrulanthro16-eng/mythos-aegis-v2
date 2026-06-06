"""Verify RAG tables and embedding column type after migration."""

import asyncio
import asyncpg


async def main() -> None:
    conn = await asyncpg.connect(
        "postgresql://postgres:postgres@localhost:5432/mythos_aegis"
    )
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    print("Tables:")
    for r in rows:
        print(" ", r["table_name"])

    col = await conn.fetch(
        "SELECT column_name, data_type, udt_name "
        "FROM information_schema.columns "
        "WHERE table_name='document_chunks' AND column_name='embedding'"
    )
    for c in col:
        print(
            f"\ndocument_chunks.embedding: "
            f"data_type={c['data_type']}, udt={c['udt_name']}"
        )

    await conn.close()


asyncio.run(main())
