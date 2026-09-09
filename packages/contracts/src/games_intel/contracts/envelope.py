from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CloudEvent[DataT](BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    specversion: Literal["1.0"]
    id: str
    source: str
    type: str
    time: datetime
    datacontenttype: Literal["application/json"] = "application/json"
    dataschema: str
    subject: str
    idempotencykey: str = Field(min_length=1)
    data: DataT
    runid: UUID | None = None
    traceparent: str | None = None

    @field_validator("time")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            msg = "time must be timezone-aware UTC"
            raise ValueError(msg)
        return value
