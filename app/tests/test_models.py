from typing import cast

from sqlalchemy import Table
from sqlalchemy import inspect as sa_inspect

from app.db.models.order import Order, OrderStatus
from app.db.models.product import Product
from app.db.models.user import User


def _tbl(model_cls: type) -> Table:
    return cast(Table, model_cls.__table__)  # type: ignore[attr-defined]


# --- Table names ---


def test_user_tablename() -> None:
    assert User.__tablename__ == "users"


def test_product_tablename() -> None:
    assert Product.__tablename__ == "products"


def test_order_tablename() -> None:
    assert Order.__tablename__ == "orders"


# --- Column presence ---


def test_user_columns_present() -> None:
    col_names = {c.name for c in _tbl(User).columns}
    assert {
        "id",
        "tenant_id",
        "email",
        "is_active",
        "created_at",
        "updated_at",
        "deleted_at",
    } <= col_names


def test_product_columns_present() -> None:
    col_names = {c.name for c in _tbl(Product).columns}
    assert {
        "id",
        "tenant_id",
        "name",
        "sku",
        "price",
        "created_at",
        "updated_at",
    } <= col_names


def test_order_columns_present() -> None:
    col_names = {c.name for c in _tbl(Order).columns}
    assert {
        "id",
        "tenant_id",
        "user_id",
        "product_id",
        "status",
        "quantity",
        "total_amount",
        "cancellable_until",
        "created_at",
        "updated_at",
    } <= col_names


# --- Index presence ---


def test_user_composite_indexes() -> None:
    index_names = {idx.name for idx in _tbl(User).indexes}
    assert "ix_user_tenant_id_id" in index_names
    assert "ix_user_tenant_id_created_at" in index_names


def test_product_composite_indexes() -> None:
    index_names = {idx.name for idx in _tbl(Product).indexes}
    assert "ix_product_tenant_id_id" in index_names
    assert "ix_product_tenant_id_created_at" in index_names


def test_order_composite_indexes() -> None:
    index_names = {idx.name for idx in _tbl(Order).indexes}
    assert "ix_order_tenant_id_id" in index_names
    assert "ix_order_tenant_id_status" in index_names
    assert "ix_order_tenant_id_created_at" in index_names


# --- Constraints ---


def test_user_email_unique() -> None:
    email_col = _tbl(User).c["email"]
    assert email_col.unique


def test_product_tenant_sku_unique_constraint() -> None:
    constraint_names = {c.name for c in _tbl(Product).constraints}
    assert "uq_product_tenant_sku" in constraint_names


# --- Foreign keys ---


def test_order_fk_to_users() -> None:
    fk_targets = {fk.target_fullname for fk in _tbl(Order).foreign_keys}
    assert "users.id" in fk_targets


def test_order_fk_to_products() -> None:
    fk_targets = {fk.target_fullname for fk in _tbl(Order).foreign_keys}
    assert "products.id" in fk_targets


# --- Relationships ---


def test_user_has_orders_relationship() -> None:
    mapper = sa_inspect(User)
    assert "orders" in {r.key for r in mapper.relationships}


def test_product_has_orders_relationship() -> None:
    mapper = sa_inspect(Product)
    assert "orders" in {r.key for r in mapper.relationships}


def test_order_has_user_relationship() -> None:
    mapper = sa_inspect(Order)
    assert "user" in {r.key for r in mapper.relationships}


def test_order_has_product_relationship() -> None:
    mapper = sa_inspect(Order)
    assert "product" in {r.key for r in mapper.relationships}


# --- OrderStatus enum ---


def test_order_status_values() -> None:
    values = {s.value for s in OrderStatus}
    assert values == {"pending", "confirmed", "shipped", "delivered", "cancelled"}


def test_order_status_cancelled_present() -> None:
    assert OrderStatus.CANCELLED.value == "cancelled"


# --- Soft delete column ---


def test_user_has_deleted_at() -> None:
    assert "deleted_at" in _tbl(User).c


def test_order_has_deleted_at() -> None:
    assert "deleted_at" in _tbl(Order).c


# --- SoftDeleteMixin property ---


def test_soft_delete_mixin_is_deleted_false_by_default() -> None:
    user = User()
    assert user.is_deleted is False


def test_soft_delete_mixin_is_deleted_true_when_set() -> None:
    from datetime import UTC, datetime

    user = User()
    user.deleted_at = datetime.now(UTC)
    assert user.is_deleted is True
