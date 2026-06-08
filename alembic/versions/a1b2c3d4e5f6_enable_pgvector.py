"""Enable pgvector extension and upgrade embedding column.

Revision ID: a1b2c3d4e5f6
Revises: d7b3e1f4a2c8
Create Date: 2026-06-08 00:00:00.000000

What this migration does
------------------------
1.  Tries to enable the ``vector`` PostgreSQL extension (pgvector).
2.  If the extension is NOT installed on this PostgreSQL instance, the
    migration logs a warning and exits cleanly — it is recorded as applied
    but makes no schema changes.  Re-run after installing pgvector.
3.  If the extension IS available:
    a.  ``CREATE EXTENSION IF NOT EXISTS vector``
    b.  ``ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768)``
        using a safe USING cast from ``double precision[]``.
    c.  ``CREATE INDEX ix_chunk_embedding_ivfflat`` using IVFFlat cosine ops
        (wrapped in contextlib.suppress so a pre-existing index is harmless).

Prerequisite
------------
pgvector must be installed before this migration can apply the column change.

Windows install guide (one-time, manual):
  See docs/release/PGVECTOR_INSTALL.md

After installing pgvector and this migration was already recorded as a no-op:
  alembic downgrade d7b3e1f4a2c8
  alembic upgrade head

Why double precision[] → vector(768)?
--------------------------------------
``double precision[]`` stores 8 bytes per float.  pgvector's ``vector(768)``
stores 4 bytes per float (float4), halving storage for each chunk embedding.
More importantly, the ``<=>`` cosine distance operator and the IVFFlat ANN
index become available, enabling fast SQL-side nearest-neighbour search
instead of fetching all embeddings into Python (current numpy approach).

Down migration
--------------
Reverts the column back to ``double precision[]`` and drops the IVFFlat index.
The vector extension is left in place (it may be used by other schemas).
"""

from __future__ import annotations

import contextlib
import logging

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "d7b3e1f4a2c8"
branch_labels: str | None = None
depends_on: str | None = None

logger = logging.getLogger("alembic.runtime.migration")

_TABLE = "document_chunks"
_COL = "embedding"
_IDX = "ix_chunk_embedding_ivfflat"
_LISTS = 100  # IVFFlat lists; rule of thumb: sqrt(row_count)


def _pgvector_available(conn: sa.engine.Connection) -> bool:
    """Return True if the vector extension is present in pg_available_extensions."""
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'vector'"
        )
    )
    return bool(result.scalar())


def upgrade() -> None:
    conn = op.get_bind()

    if not _pgvector_available(conn):
        logger.warning(
            "pgvector extension is not installed on this PostgreSQL instance. "
            "Skipping embedding column upgrade. "
            "Install pgvector (see docs/release/PGVECTOR_INSTALL.md), then run: "
            "alembic downgrade d7b3e1f4a2c8 && alembic upgrade head"
        )
        return

    # Enable extension
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Upgrade embedding column: double precision[] → vector(768)
    # The USING cast truncates or pads if the stored array length != 768;
    # for correctly-indexed chunks this is always exactly 768 floats.
    conn.execute(
        sa.text(
            f"ALTER TABLE {_TABLE} "
            f"ALTER COLUMN {_COL} TYPE vector(768) "
            f"USING {_COL}::vector(768)"
        )
    )

    logger.info("pgvector: embedding column upgraded to vector(768)")

    # IVFFlat index for approximate nearest-neighbour cosine search.
    # Wrapped so re-running is idempotent.
    with contextlib.suppress(Exception):
        conn.execute(
            sa.text(
                f"CREATE INDEX {_IDX} "
                f"ON {_TABLE} "
                f"USING ivfflat ({_COL} vector_cosine_ops) "
                f"WITH (lists = {_LISTS})"
            )
        )
        logger.info("pgvector: IVFFlat index created (lists=%d)", _LISTS)


def downgrade() -> None:
    conn = op.get_bind()

    # Check if the column is currently vector type before trying to revert
    result = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c",
        ),
        {"t": _TABLE, "c": _COL},
    )
    row = result.fetchone()
    if row is None or "USER-DEFINED" not in str(row[0]).upper():
        # Column is already double precision[] — no-op or already reverted.
        logger.info("pgvector downgrade: column already double precision[]")
        return

    # Drop IVFFlat index
    with contextlib.suppress(Exception):
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {_IDX}"))

    # Revert column to double precision[]
    conn.execute(
        sa.text(
            f"ALTER TABLE {_TABLE} "
            f"ALTER COLUMN {_COL} TYPE double precision[] "
            f"USING {_COL}::double precision[]"
        )
    )

    logger.info("pgvector downgrade: embedding column reverted to double precision[]")
    # Note: we leave the vector extension in place.
