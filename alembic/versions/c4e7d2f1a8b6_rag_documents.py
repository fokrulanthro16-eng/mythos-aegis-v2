"""RAG documents and document_chunks tables.

Revision ID: c4e7d2f1a8b6
Revises: b2f4e8a1c3d5
Create Date: 2026-06-06 00:00:00.000000

Tables created
--------------
documents       — tenant-scoped document metadata (filename, status, soft-delete)
document_chunks — text chunks with float-array embeddings for similarity search

Vector support
--------------
Embedding column uses PostgreSQL ARRAY(FLOAT4) for maximum portability — no
pgvector extension required.  Similarity search is done in application code
using numpy cosine similarity (see repository.py DocumentChunkRepository).

If pgvector becomes available, a follow-up migration can ALTER the column to
vector(768) and add an IVFFlat index for ANN acceleration.

Indexes
-------
- tenant_id + created_at  on both tables
- tenant_id + project_id  on both tables
- document_id             on document_chunks (FK lookup)
- content_hash            on document_chunks (dedup check)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4e7d2f1a8b6"
down_revision: str | None = "b2f4e8a1c3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pgvector extension intentionally NOT required — embedding column uses
    # ARRAY(FLOAT4) which works on any PostgreSQL installation.

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column(
            "source_type",
            sa.String(50),
            nullable=False,
            server_default="upload",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_tenant_id", "documents", ["tenant_id"])
    op.create_index("ix_document_project_id", "documents", ["project_id"])
    op.create_index(
        "ix_document_tenant_created_at", "documents", ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_document_tenant_project", "documents", ["tenant_id", "project_id"]
    )

    # ── document_chunks ───────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "token_estimate",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("embedding", sa.ARRAY(sa.Float(precision=32)), nullable=True),
        sa.Column("citation_label", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunk_tenant_id", "document_chunks", ["tenant_id"])
    op.create_index("ix_chunk_project_id", "document_chunks", ["project_id"])
    op.create_index("ix_chunk_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_chunk_content_hash", "document_chunks", ["content_hash"])
    op.create_index(
        "ix_chunk_tenant_created_at",
        "document_chunks",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_chunk_tenant_project",
        "document_chunks",
        ["tenant_id", "project_id"],
    )

    # IVFFlat index omitted — requires pgvector extension.
    # A follow-up migration can add it once pgvector is installed.


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
    # Do NOT drop the vector extension — it may be used by other schemas.
