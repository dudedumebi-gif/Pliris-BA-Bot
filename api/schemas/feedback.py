from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """Request model for creating feedback."""

    conversation_id: str
    message_id: str
    rating: int = Field(..., ge=1, le=5)
    helpful: str = Field(..., pattern="^(Yes|No|Partially)$")
    categories: list[str] = []
    comments: str | None = None


class FeedbackAnalytics(BaseModel):
    """Response model for feedback analytics."""

    total: int
    avg_rating: float
    helpful_percentage: float
    response_rate: float
    categories: dict
    recent_feedback: list[dict]
