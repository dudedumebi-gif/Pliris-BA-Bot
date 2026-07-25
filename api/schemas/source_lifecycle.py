from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceLifecycleAction = Literal["archive", "restore"]
SourceLifecycleStatus = Literal["ready", "archived"]


class SourceLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=500)
    confirmation: str = Field(min_length=1, max_length=200)

    @field_validator("reason", "confirmation", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class SourceLifecycleEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    document_id: UUID
    action: SourceLifecycleAction
    actor: str
    reason: str
    previous_status: SourceLifecycleStatus
    new_status: SourceLifecycleStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SourceLifecycleEventListResponse(BaseModel):
    document_id: UUID
    items: list[SourceLifecycleEvent]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
