from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.conversation_tokens import (
    ConversationAccessDenied,
    ConversationTokenManager,
    MalformedConversationToken,
    get_conversation_token_manager,
)
from api.guest_access import get_guest_user
from api.schemas.chat import ChatRequest, ChatResponse
from pliris.agents.conversation_context import (
    ConversationContextResolver,
    ConversationResolution,
)
from pliris.agents.grounded_orchestrator import GroundedResponseOrchestrator
from pliris.agents.request_classifier import RequestClassifier
from pliris.database.repositories.conversation_history import (
    ConversationHistoryRepository,
)
from pliris.database.repositories.grounded_persistence import (
    GroundedPersistenceRepository,
)
from pliris.guardrails.prompt_injection import PromptInjectionDetector
from pliris.guardrails.scope_classifier import ScopeClassifier

logger = logging.getLogger(__name__)

OUT_OF_SCOPE_RESPONSE = (
    "Pliris BA Bot is designed to assist with Business Analysis, "
    "Business Systems Analysis, and Project Management practices. "
    "Please ask a question related to one of these areas."
)

SCOPE_CLARIFICATION_RESPONSE = (
    "Please clarify how this question relates to Business Analysis, "
    "Business Systems Analysis, or Project Management so Pliris can "
    "route it correctly."
)

router = APIRouter()


@lru_cache
def get_grounded_orchestrator() -> GroundedResponseOrchestrator:
    """Return the production grounded response pipeline."""

    return GroundedResponseOrchestrator(persistence_repository=GroundedPersistenceRepository())


@lru_cache
def get_scope_classifier() -> ScopeClassifier:
    """Return the configured query scope classifier."""

    return ScopeClassifier()


@lru_cache
def get_request_classifier() -> RequestClassifier:
    """Return the deterministic request-mode classifier."""

    return RequestClassifier()


@lru_cache
def get_prompt_injection_detector() -> PromptInjectionDetector:
    """Return the prompt-injection detector."""

    return PromptInjectionDetector()


@lru_cache
def get_conversation_history_repository() -> ConversationHistoryRepository:
    """Return the bounded conversation-history reader."""

    return ConversationHistoryRepository()


@lru_cache
def get_conversation_context_resolver() -> ConversationContextResolver:
    """Return the deterministic follow-up resolver."""

    return ConversationContextResolver()


get_system_user = get_guest_user

UserDependency = Annotated[dict[str, str], Depends(get_system_user)]
OrchestratorDependency = Annotated[
    GroundedResponseOrchestrator,
    Depends(get_grounded_orchestrator),
]
ScopeClassifierDependency = Annotated[
    ScopeClassifier,
    Depends(get_scope_classifier),
]
RequestClassifierDependency = Annotated[
    RequestClassifier,
    Depends(get_request_classifier),
]
InjectionDetectorDependency = Annotated[
    PromptInjectionDetector,
    Depends(get_prompt_injection_detector),
]
ConversationTokenDependency = Annotated[
    ConversationTokenManager,
    Depends(get_conversation_token_manager),
]
ConversationHistoryDependency = Annotated[
    ConversationHistoryRepository,
    Depends(get_conversation_history_repository),
]
ConversationContextDependency = Annotated[
    ConversationContextResolver,
    Depends(get_conversation_context_resolver),
]


@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    user: UserDependency,
    orchestrator: OrchestratorDependency,
    scope_classifier: ScopeClassifierDependency,
    request_classifier: RequestClassifierDependency,
    prompt_injection_detector: InjectionDetectorDependency,
    conversation_tokens: ConversationTokenDependency,
    conversation_history: ConversationHistoryDependency,
    context_resolver: ConversationContextDependency,
) -> ChatResponse:
    """FastAPI dependency-injected public chat endpoint."""

    return await chat(
        request=request,
        user=user,
        orchestrator=orchestrator,
        scope_classifier=scope_classifier,
        request_classifier=request_classifier,
        prompt_injection_detector=prompt_injection_detector,
        conversation_tokens=conversation_tokens,
        conversation_history=conversation_history,
        context_resolver=context_resolver,
    )


async def chat(
    request: ChatRequest,
    user: dict[str, str],
    orchestrator: GroundedResponseOrchestrator,
    scope_classifier: ScopeClassifier,
    request_classifier: RequestClassifier,
    prompt_injection_detector: PromptInjectionDetector,
    *,
    conversation_tokens: ConversationTokenManager | None = None,
    conversation_history: ConversationHistoryRepository | None = None,
    context_resolver: ConversationContextResolver | None = None,
) -> ChatResponse:
    """Process a user message through the guarded grounded pipeline."""

    try:
        if prompt_injection_detector.detect(request.message):
            logger.warning(
                "Prompt injection detected from user %s",
                user["id"],
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Potential prompt injection detected",
            )

        conversation_id = request.conversation_id
        resolution = _standalone_resolution(request.message)
        session_id = user.get("session_id")

        if session_id is not None:
            token_manager = conversation_tokens or get_conversation_token_manager()
            history_repository = conversation_history or get_conversation_history_repository()
            resolver = context_resolver or get_conversation_context_resolver()

            history: list[dict[str, str]] = []
            if conversation_id is not None:
                conversation_id = _validated_conversation_id(
                    token_manager,
                    conversation_id=conversation_id,
                    session_id=session_id,
                )
                history = await history_repository.get_recent_messages(
                    conversation_id,
                    limit=resolver.max_history_messages,
                )

            resolution = resolver.resolve(request.message, history)

        scope_result = await scope_classifier.classify(resolution.scope_query)
        scope_metadata = _scope_metadata(scope_result)

        if scope_result.get("requires_clarification", False):
            return ChatResponse(
                response=SCOPE_CLARIFICATION_RESPONSE,
                citations=[],
                confidence=0.0,
                scope=str(scope_result["category"]),
                conversation_id=conversation_id,
                metadata={
                    "insufficient_evidence": False,
                    "guardrail": "scope_clarification",
                    "scope_decision": scope_metadata,
                    "conversation_context": resolution.metadata(),
                },
            )

        if not scope_result["in_scope"]:
            logger.info(
                "Query classified out of scope for user %s",
                user["id"],
            )
            return ChatResponse(
                response=OUT_OF_SCOPE_RESPONSE,
                citations=[],
                confidence=0.0,
                scope=scope_result["category"],
                conversation_id=conversation_id,
                metadata={
                    "insufficient_evidence": False,
                    "guardrail": "out_of_scope",
                    "scope_decision": scope_metadata,
                    "conversation_context": resolution.metadata(),
                },
            )

        if session_id is not None and conversation_id is None:
            token_manager = conversation_tokens or get_conversation_token_manager()
            conversation_id = token_manager.issue(session_id)

        classified_message = (
            resolution.generation_question if resolution.context_used else request.message
        )
        request_classification = request_classifier.classify(classified_message)

        pipeline_arguments: dict[str, Any] = {
            "message": request.message,
            "conversation_id": conversation_id,
            "user_id": user["id"],
            "document_id": _document_id(request.context),
            "scope_status": "in_scope",
            "scope_confidence": _scope_confidence(scope_result),
            "scope_category": scope_result["category"],
            "request_mode": request_classification.mode.value,
        }
        if resolution.context_used:
            pipeline_arguments.update(
                {
                    "retrieval_query": resolution.retrieval_query,
                    "generation_question": resolution.generation_question,
                }
            )

        result = await orchestrator.process_query(**pipeline_arguments)
        result_data = result.to_dict()

        return ChatResponse(
            response=result_data["response"],
            citations=result_data["citations"],
            confidence=result_data["confidence"],
            scope=scope_result["category"],
            conversation_id=result_data["conversation_id"],
            metadata={
                "insufficient_evidence": result_data["insufficient_evidence"],
                "model": result_data["model"],
                "response_id": result_data["response_id"],
                "usage": result_data["usage"],
                "request_mode": request_classification.mode.value,
                "request_mode_confidence": (request_classification.confidence),
                "request_mode_rule": request_classification.matched_rule,
                "scope_decision": scope_metadata,
                "conversation_context": resolution.metadata(),
                **result_data["metadata"],
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error processing chat request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request",
        ) from exc


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> None:
    """Return not implemented until streaming support is added."""

    del request
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Streaming not yet implemented",
    )


def _validated_conversation_id(
    token_manager: ConversationTokenManager,
    *,
    conversation_id: str,
    session_id: str,
) -> str:
    try:
        return token_manager.validate(conversation_id, session_id)
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


def _standalone_resolution(message: str) -> ConversationResolution:
    normalized = " ".join(message.split())
    return ConversationResolution(
        original_message=normalized,
        scope_query=normalized,
        retrieval_query=normalized,
        generation_question=normalized,
        context_used=False,
        history_message_count=0,
    )


def _document_id(context: dict[str, Any] | None) -> str | None:
    if not context:
        return None

    value = context.get("document_id")
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    return normalized or None


def _scope_metadata(
    scope_result: dict[str, Any],
) -> dict[str, Any]:
    """Return non-duplicative semantic routing metadata."""

    return {
        key: value for key, value in scope_result.items() if key not in {"category", "in_scope"}
    }


def _scope_confidence(
    scope_result: dict[str, Any],
) -> float | None:
    value = scope_result.get("confidence")
    if value is None:
        return None

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None

    if 0.0 <= confidence <= 1.0:
        return confidence
    return None
