from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation returned with a grounded chat answer."""

    source: str
    title: str
    text: str
    page: int | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    citation_id: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    rank: int | None = Field(default=None, ge=1)
    document_id: str | None = None


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""

    response: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    scope: str
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
