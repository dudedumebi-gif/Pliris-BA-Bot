from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation model for retrieved documents."""

    source: str
    title: str
    text: str
    page: int | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    metadata: dict | None = None


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    context: dict | None = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str
    citations: list[Citation] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    scope: str
    conversation_id: str | None = None
    metadata: dict | None = None
