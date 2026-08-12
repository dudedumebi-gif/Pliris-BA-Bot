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


class MonitoringDashboardSummary(BaseModel):
    """Aggregate metrics that never expose message text or guest identifiers."""

    model_config = ConfigDict(extra="forbid")

    total_responses: int = Field(ge=0)
    active_conversations: int = Field(ge=0)
    in_scope_responses: int = Field(ge=0)
    borderline_responses: int = Field(ge=0)
    out_of_scope_responses: int = Field(ge=0)
    latency_samples: int = Field(ge=0)
    avg_latency_ms: float | None = Field(default=None, ge=0)
    p95_latency_ms: float | None = Field(default=None, ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    token_samples: int = Field(ge=0)
    feedback_records: int = Field(ge=0)
    helpful_feedback: int = Field(ge=0)
    unhelpful_feedback: int = Field(ge=0)
    commented_feedback: int = Field(ge=0)
    request_failures: int = Field(ge=0)
    prompt_injection_blocks: int = Field(ge=0)
    feedback_submissions: int = Field(ge=0)


class MonitoringTimePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    count: int = Field(ge=0)


class MonitoringNamedCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    count: int = Field(ge=0)


class MonitoringLatencyBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=32)
    count: int = Field(ge=0)


class MonitoringModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class MonitoringDashboardResponse(BaseModel):
    """Protected dashboard snapshot built only from aggregate projections."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime
    since_hours: int = Field(ge=1, le=720)
    bucket: Literal["hour", "day"]
    summary: MonitoringDashboardSummary
    response_timeline: list[MonitoringTimePoint]
    scope_breakdown: list[MonitoringNamedCount]
    latency_distribution: list[MonitoringLatencyBucket]
    failure_breakdown: list[MonitoringNamedCount]
    model_usage: list[MonitoringModelUsage]
