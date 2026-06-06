from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True)
class AuditRecord:
    request_id: UUID
    tenant_id: UUID
    user_id: UUID
    order_id: UUID
    action: str
    timestamp: datetime


def build_audit_record(
    *,
    request_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    order_id: UUID,
    action: str,
) -> AuditRecord:
    return AuditRecord(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        order_id=order_id,
        action=action,
        timestamp=datetime.now(UTC),
    )
