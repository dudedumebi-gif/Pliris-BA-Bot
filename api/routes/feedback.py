from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.conversation_tokens import (
    ConversationAccessDenied,
    ConversationTokenManager,
    MalformedConversationToken,
    get_conversation_token_manager,
)
from api.guest_access import get_guest_user
from api.schemas.feedback import FeedbackCreate, FeedbackResponse
from pliris.database.repositories.feedback import (
    FeedbackRepository,
    FeedbackTargetNotFoundError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_feedback_repository() -> FeedbackRepository:
    return FeedbackRepository()


UserDependency = Annotated[dict[str, str], Depends(get_guest_user)]
ConversationTokenDependency = Annotated[
    ConversationTokenManager,
    Depends(get_conversation_token_manager),
]
FeedbackRepositoryDependency = Annotated[
    FeedbackRepository,
    Depends(get_feedback_repository),
]


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackCreate,
    user: UserDependency,
    conversation_tokens: ConversationTokenDependency,
    repository: FeedbackRepositoryDependency,
) -> FeedbackResponse:
    """Create or replace feedback for one persisted assistant response."""

    session_id = user.get("session_id")
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feedback access is not authorized.",
        )

    try:
        conversation_id = conversation_tokens.validate(
            request.conversation_id,
            session_id,
        )
    except MalformedConversationToken as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation identifier.",
        ) from exc
    except ConversationAccessDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conversation access is not authorized.",
        ) from exc

    try:
        result = await repository.upsert(
            client_session_id=conversation_id,
            assistant_message_id=request.assistant_message_id,
            rating=request.rating,
            citation_helpful=request.citation_helpful,
            scope_decision_correct=request.scope_decision_correct,
            comment=request.comment,
        )
    except FeedbackTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback target was not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback values are not valid.",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to persist response feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback.",
        ) from exc

    return FeedbackResponse.model_validate({**result, "status": "submitted"})
