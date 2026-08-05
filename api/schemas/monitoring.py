from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MonitoringEventItem(BaseModel):
    """Developer-safe projection of one operational event."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    severity: Literal["debug", "info", "warning", "error", "critical"]
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MonitoringEventListResponse(BaseModel):
    items: list[MonitoringEventItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    since_hours: int = Field(ge=1, le=720)
