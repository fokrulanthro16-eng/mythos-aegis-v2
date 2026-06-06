from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnalyticsRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sql: str
    user_id: UUID
    start_date: date | None = None
    end_date: date | None = None


class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: list[dict[str, object]]
    row_count: int
