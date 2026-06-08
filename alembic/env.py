"""Alembic migration environment — async SQLAlchemy (asyncpg / PostgreSQL).

Runtime behaviour
-----------------
- DATABASE_URL from the environment overrides the alembic.ini placeholder.
- All ORM models are imported here so that autogenerate detects every table.
- Migrations run through an async engine (run_sync pattern) so the same
  asyncpg driver used by the application is used for schema changes.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.db.base import Base
from app.db.models import Order, Product, User  # noqa: F401

# DB_SSL_REQUIRE=true is needed for TLS-only hosts (Supabase, RDS, Cloud SQL).
_ssl_connect_args: dict[str, str] = (
    {"ssl": "require"}
    if os.environ.get("DB_SSL_REQUIRE", "").lower() == "true"
    else {}
)

# ── Alembic config object ─────────────────────────────────────────────────────
alembic_cfg = context.config

if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# Override sqlalchemy.url with DATABASE_URL from the environment when set.
_env_db_url = os.environ.get("DATABASE_URL")
if _env_db_url:
    alembic_cfg.set_main_option("sqlalchemy.url", _env_db_url)

target_metadata = Base.metadata


# ── Offline mode (generates SQL without connecting) ───────────────────────────


def run_migrations_offline() -> None:
    url = alembic_cfg.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (connects and applies migrations) ─────────────────────────────


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    section: dict[str, Any] = alembic_cfg.get_section(
        alembic_cfg.config_ini_section, {}
    )
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_ssl_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
