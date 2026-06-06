from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CancelOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: UUID


class CancelOrderResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_status: str
    order_id: UUID
    cancelled_at: datetime
