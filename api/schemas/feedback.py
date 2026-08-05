from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeedbackRating = Literal[-1, 1]


class FeedbackCreate(BaseModel):
    """Response-bound feedback submitted by one validated guest session."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1, max_length=200)
    assistant_message_id: UUID
    rating: FeedbackRating
    citation_helpful: bool | None = None
    scope_decision_correct: bool | None = None
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("conversation_id", mode="before")
    @classmethod
    def strip_conversation_id(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_comment(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None


class FeedbackResponse(BaseModel):
    """Persisted feedback state for one assistant response."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    assistant_message_id: UUID
    rating: FeedbackRating
    citation_helpful: bool | None
    scope_decision_correct: bool | None
    comment: str | None
    created_at: datetime
    status: Literal["submitted"] = "submitted"
