from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.conversation_tokens import (
    ConversationAccessDenied,
    ConversationTokenManager,
    MalformedConversationToken,
    get_conversation_token_manager,
)
from api.developer_access import require_developer_access
from api.guest_access import get_guest_user
from api.schemas.feedback import (
    FeedbackCreate,
    FeedbackListResponse,
    FeedbackResponse,
    FeedbackStats,
)
from pliris.database.repositories.feedback import (
    FeedbackRepository,
    FeedbackTargetNotFoundError,
)
from pliris.monitoring.events import EventLogger

logger = logging.getLogger(__name__)
router = APIRouter()


def get_feedback_repository() -> FeedbackRepository:
    return FeedbackRepository()


@lru_cache
def get_event_logger() -> EventLogger:
    """Return the fail-open operational event recorder."""

    return EventLogger()


UserDependency = Annotated[dict[str, str], Depends(get_guest_user)]
ConversationTokenDependency = Annotated[
    ConversationTokenManager,
    Depends(get_conversation_token_manager),
]
FeedbackRepositoryDependency = Annotated[
    FeedbackRepository,
    Depends(get_feedback_repository),
]
EventLoggerDependency = Annotated[
    EventLogger,
    Depends(get_event_logger),
]


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackCreate,
    user: UserDependency,
    conversation_tokens: ConversationTokenDependency,
    repository: FeedbackRepositoryDependency,
    event_logger: EventLoggerDependency,
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
        await event_logger.log_feedback_failure(
            reason="target_not_found",
            message_id=request.assistant_message_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback target was not found.",
        ) from exc
    except ValueError as exc:
        await event_logger.log_feedback_failure(
            reason="invalid_values",
            message_id=request.assistant_message_id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback values are not valid.",
        ) from exc
    except Exception as exc:
        await event_logger.log_feedback_failure(
            reason="repository_error",
            message_id=request.assistant_message_id,
        )
        logger.exception("Failed to persist response feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback.",
        ) from exc

    await event_logger.log_feedback_submitted(
        message_id=request.assistant_message_id,
        rating=request.rating,
        has_comment=request.comment is not None,
        citation_answered=request.citation_helpful is not None,
        scope_answered=request.scope_decision_correct is not None,
    )
    return FeedbackResponse.model_validate({**result, "status": "submitted"})


@router.get(
    "/stats",
    response_model=FeedbackStats,
    dependencies=[Depends(require_developer_access)],
)
async def get_feedback_stats(
    repository: FeedbackRepositoryDependency,
) -> FeedbackStats:
    """Return protected aggregate feedback counts."""

    try:
        return FeedbackStats.model_validate(await repository.get_stats())
    except Exception as exc:
        logger.exception("Failed to fetch feedback statistics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch feedback statistics.",
        ) from exc


@router.get(
    "/",
    response_model=FeedbackListResponse,
    dependencies=[Depends(require_developer_access)],
)
async def list_feedback(
    repository: FeedbackRepositoryDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    rating: Annotated[int | None, Query()] = None,
    citation_helpful: Annotated[bool | None, Query()] = None,
    scope_decision_correct: Annotated[bool | None, Query()] = None,
) -> FeedbackListResponse:
    """List protected response-level feedback without guest identifiers."""

    if rating is not None and rating not in {-1, 1}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="rating must be -1 or 1.",
        )

    try:
        items, total = await repository.list_feedback(
            limit=limit,
            offset=offset,
            rating=rating,
            citation_helpful=citation_helpful,
            scope_decision_correct=scope_decision_correct,
        )
        return FeedbackListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.exception("Failed to list response feedback")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch response feedback.",
        ) from exc
