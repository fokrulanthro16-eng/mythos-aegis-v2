"""One-shot script: ensure mythos_aegis DB exists and check pgvector extension."""

import asyncio
import asyncpg


async def main() -> None:
    # Connect to postgres (maintenance DB) to check/create mythos_aegis
    conn = await asyncpg.connect(
        "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    try:
        rows = await conn.fetch(
            "SELECT datname FROM pg_database WHERE datname = 'mythos_aegis'"
        )
        if rows:
            print("DB_EXISTS: mythos_aegis")
        else:
            await conn.execute("CREATE DATABASE mythos_aegis")
            print("DB_CREATED: mythos_aegis")
    finally:
        await conn.close()

    # Now connect to mythos_aegis and check extensions
    conn2 = await asyncpg.connect(
        "postgresql://postgres:postgres@localhost:5432/mythos_aegis"
    )
    try:
        ext = await conn2.fetch(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        )
        print(f"PGVECTOR_INSTALLED: {bool(ext)}")

        # Try to install pgvector if not present
        if not ext:
            try:
                await conn2.execute("CREATE EXTENSION IF NOT EXISTS vector")
                print("PGVECTOR_CREATED")
            except Exception as e:
                print(f"PGVECTOR_ERROR: {e}")
    finally:
        await conn2.close()


asyncio.run(main())
