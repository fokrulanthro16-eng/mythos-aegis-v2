"""Initial schema: users, products, orders.

Revision ID: aef8c3b72d1a
Revises:
Create Date: 2026-06-05 00:00:00.000000

Tables created
--------------
users       — multi-tenant user accounts with soft-delete and timestamps
products    — per-tenant product catalogue (sku unique per tenant)
orders      — order records with status enum, FK to users + products

All tables carry:
  - UUID primary key
  - tenant_id (multi-tenancy)
  - created_at / updated_at (UTC timestamps, server-side default)
  - deleted_at  (soft-delete; NULL means not deleted)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "aef8c3b72d1a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_user_tenant_id_id", "users", ["tenant_id", "id"])
    op.create_index(
        "ix_user_tenant_id_created_at", "users", ["tenant_id", "created_at"]
    )

    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])
    op.create_index("ix_product_tenant_id_id", "products", ["tenant_id", "id"])
    op.create_index(
        "ix_product_tenant_id_created_at", "products", ["tenant_id", "created_at"]
    )

    # ── orders ────────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "shipped",
                "delivered",
                "cancelled",
                name="order_status_enum",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "quantity",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("total_amount", sa.Numeric(12, 4), nullable=False),
        sa.Column("cancellable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_orders_user_id"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_orders_product_id"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
    )
    op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_product_id", "orders", ["product_id"])
    op.create_index("ix_order_tenant_id_id", "orders", ["tenant_id", "id"])
    op.create_index("ix_order_tenant_id_status", "orders", ["tenant_id", "status"])
    op.create_index(
        "ix_order_tenant_id_created_at", "orders", ["tenant_id", "created_at"]
    )


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_index("ix_order_tenant_id_created_at", table_name="orders")
    op.drop_index("ix_order_tenant_id_status", table_name="orders")
    op.drop_index("ix_order_tenant_id_id", table_name="orders")
    op.drop_index("ix_orders_product_id", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_orders_tenant_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_product_tenant_id_created_at", table_name="products")
    op.drop_index("ix_product_tenant_id_id", table_name="products")
    op.drop_index("ix_products_tenant_id", table_name="products")
    op.drop_table("products")

    op.drop_index("ix_user_tenant_id_created_at", table_name="users")
    op.drop_index("ix_user_tenant_id_id", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
