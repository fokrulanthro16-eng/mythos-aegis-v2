from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class TableMetadata:
    name: str
    allowed_columns: frozenset[str]


ALLOWED_TABLES: Final[dict[str, TableMetadata]] = {
    "users": TableMetadata(
        name="users",
        allowed_columns=frozenset(
            {
                "id",
                "tenant_id",
                "email",
                "created_at",
                "updated_at",
                "deleted_at",
            }
        ),
    ),
    "products": TableMetadata(
        name="products",
        allowed_columns=frozenset(
            {
                "id",
                "tenant_id",
                "sku",
                "name",
                "price",
                "created_at",
                "updated_at",
                "deleted_at",
            }
        ),
    ),
    "orders": TableMetadata(
        name="orders",
        allowed_columns=frozenset(
            {
                "id",
                "tenant_id",
                "user_id",
                "product_id",
                "status",
                "created_at",
                "updated_at",
                "deleted_at",
                "cancellable_until",
            }
        ),
    ),
}

BLOCKED_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "password_hash",
        "api_token",
        "api_tokens",
        "secret_payload",
        "private_notes",
        "internal_risk_score",
    }
)
