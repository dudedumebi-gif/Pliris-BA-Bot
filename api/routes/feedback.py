import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.feedback import FeedbackAnalytics, FeedbackCreate
from pliris.database.repositories.feedback import FeedbackRepository

logger = logging.getLogger(__name__)

router = APIRouter()
feedback_repo = FeedbackRepository()


@router.post("/")
async def submit_feedback(
    feedback: FeedbackCreate, user: dict = Depends(lambda: {"id": "system", "name": "System User"})
):
    """
    Submit feedback for a conversation response.
    """
    try:
        feedback_id = await feedback_repo.create(
            conversation_id=feedback.conversation_id,
            message_id=feedback.message_id,
            user_id=user["id"],
            rating=feedback.rating,
            helpful=feedback.helpful,
            categories=feedback.categories,
            comments=feedback.comments,
        )

        logger.info(f"Feedback submitted: {feedback_id}")
        return {"id": feedback_id, "status": "submitted"}

    except Exception as exc:
        logger.error(f"Error submitting feedback: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit feedback"
        ) from exc


@router.get("/conversations")
async def get_recent_conversations(
    limit: int = 10, user: dict = Depends(lambda: {"id": "system", "name": "System User"})
):
    """
    Get recent conversations for feedback.
    """
    try:
        conversations = await feedback_repo.get_recent_conversations(
            user_id=user["id"], limit=limit
        )
        return conversations

    except Exception as exc:
        logger.error(f"Error fetching conversations: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversations",
        ) from exc


@router.get("/analytics", response_model=FeedbackAnalytics)
async def get_feedback_analytics():
    """
    Get feedback analytics and statistics.
    """
    try:
        analytics = await feedback_repo.get_analytics()
        return analytics

    except Exception as exc:
        logger.error(f"Error fetching analytics: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch analytics"
        ) from exc
