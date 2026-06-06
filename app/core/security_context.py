from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SecurityContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_id: UUID
    current_user_id: UUID
    tenant_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]
