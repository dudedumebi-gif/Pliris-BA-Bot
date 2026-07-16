from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """Model for a retrieved text chunk."""

    id: str
    text: str
    source: str
    title: str
    page: int | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    metadata: dict | None = None


class RetrievalRequest(BaseModel):
    """Request model for retrieval."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: dict | None = None


class RetrievalResponse(BaseModel):
    """Response model for retrieval."""

    query: str
    chunks: list[RetrievedChunk]
    total_found: int
    search_method: str
