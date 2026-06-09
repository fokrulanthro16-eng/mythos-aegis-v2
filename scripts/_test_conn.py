"""Probe all viable Supabase connection endpoints for this project."""
import asyncio
import os
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(_root / ".env", override=True)


async def try_connect(url: str, label: str, timeout: float = 8.0) -> bool:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        url,
        connect_args={"ssl": "require", "timeout": timeout},
        pool_pre_ping=False,
    )
    try:
        async with engine.connect() as conn:
            row = await conn.execute(text("SELECT version()"))
            ver = (row.scalar() or "")[:60]
            print(f"  [OK] {label} -> {ver}")
            return True
    except Exception as exc:
        msg = str(exc)[:100].encode("ascii", "replace").decode()
        print(f"  [FAIL] {label}: {type(exc).__name__}: {msg}")
        return False
    finally:
        await engine.dispose()


async def main() -> None:
    import re
    raw_url = os.environ.get("DATABASE_URL", "")
    m = re.search(r"://[^:]+:([^@]+)@", raw_url)
    if not m:
        print("ERROR: Cannot extract password from DATABASE_URL in .env")
        sys.exit(1)
    pw = m.group(1)
    ref = "zpqinpucbavigyzgfsij"
    direct_host = f"db.{ref}.supabase.co"

    candidates = [
        # 1. Direct connection, IPv4 forced via numeric IP bypass (skip — IPv6 only)
        # 2. Session pooler with project-ref username (all regions already failed)
        # 3. Session pooler with plain 'postgres' username (old Supabase format)
        (f"postgresql+asyncpg://postgres:{pw}@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres",
         "session-pooler ap-se-1, user=postgres"),
        (f"postgresql+asyncpg://postgres:{pw}@aws-0-us-east-1.pooler.supabase.com:5432/postgres",
         "session-pooler us-east-1, user=postgres"),
        # 4. Direct host on port 6543 (Supavisor transaction mode via direct hostname)
        (f"postgresql+asyncpg://postgres.{ref}:{pw}@{direct_host}:6543/postgres",
         "direct-host:6543 user=postgres.ref"),
        (f"postgresql+asyncpg://postgres:{pw}@{direct_host}:6543/postgres",
         "direct-host:6543 user=postgres"),
        # 5. Direct host on port 5432 with asyncpg native (not SQLAlchemy) — DNS bypass test
    ]

    print("=== Supabase endpoint probe ===")
    winner = None
    for url, label in candidates:
        ok = await try_connect(url, label)
        if ok:
            winner = (url, label)
            break

    if winner:
        masked = winner[0].replace(pw, "***")
        print(f"\n[winner] {masked}")
    else:
        print("\n[no winner] -- trying asyncpg native with server_settings override")
        # Try asyncpg directly, forcing IPv4 via AF_INET
        try:
            import asyncpg
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    host=direct_host,
                    port=5432,
                    user="postgres",
                    password=pw,
                    database="postgres",
                    ssl=ctx,
                ),
                timeout=10,
            )
            ver = await conn.fetchval("SELECT version()")
            print(f"  [OK] asyncpg native direct: {str(ver)[:60]}")
            await conn.close()
        except Exception as exc:
            msg = str(exc)[:120].encode("ascii", "replace").decode()
            print(f"  [FAIL] asyncpg native direct: {type(exc).__name__}: {msg}")

        # Try asyncpg native on pooler with plain postgres user
        try:
            import asyncpg
            import ssl
            ctx = ssl.create_default_context()
            conn = await asyncio.wait_for(
                asyncpg.connect(
                    host="aws-0-ap-southeast-1.pooler.supabase.com",
                    port=5432,
                    user="postgres",
                    password=pw,
                    database="postgres",
                    ssl=ctx,
                ),
                timeout=10,
            )
            ver = await conn.fetchval("SELECT version()")
            print(f"  [OK] asyncpg pooler plain-user: {str(ver)[:60]}")
            await conn.close()
        except Exception as exc:
            msg = str(exc)[:120].encode("ascii", "replace").decode()
            print(f"  [FAIL] asyncpg pooler plain-user: {type(exc).__name__}: {msg}")


asyncio.run(main())
