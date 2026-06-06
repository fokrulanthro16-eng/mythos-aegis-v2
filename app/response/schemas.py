from pydantic import BaseModel, ConfigDict


class ResponsePayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str
    markdown_table: str | None = None
    chart: dict[str, object] | None = None
    warnings: list[str] = []
    request_id: str
