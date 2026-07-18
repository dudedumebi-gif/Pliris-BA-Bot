from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.chat import ChatRequest, ChatResponse
from pliris.agents.grounded_orchestrator import (
    GroundedResponseOrchestrator,
)
from pliris.agents.request_classifier import RequestClassifier
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


def get_system_user() -> dict[str, str]:
    """Return the current application user until authentication is added."""

    return {
        "id": "system",
        "name": "System User",
    }


UserDependency = Annotated[
    dict[str, str],
    Depends(get_system_user),
]
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


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: UserDependency,
    orchestrator: OrchestratorDependency,
    scope_classifier: ScopeClassifierDependency,
    request_classifier: RequestClassifierDependency,
    prompt_injection_detector: InjectionDetectorDependency,
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

        scope_result = await scope_classifier.classify(request.message)

        if not scope_result["in_scope"]:
            logger.info(
                "Query classified out of scope: %s",
                request.message,
            )
            return ChatResponse(
                response=OUT_OF_SCOPE_RESPONSE,
                citations=[],
                confidence=0.0,
                scope=scope_result["category"],
                conversation_id=request.conversation_id,
                metadata={
                    "insufficient_evidence": False,
                    "guardrail": "out_of_scope",
                },
            )

        request_classification = request_classifier.classify(request.message)

        result = await orchestrator.process_query(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=user["id"],
            document_id=_document_id(request.context),
            scope_status="in_scope",
            scope_confidence=_scope_confidence(scope_result),
            scope_category=scope_result["category"],
        )
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
                "request_mode_rule": (request_classification.matched_rule),
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


def _document_id(context: dict[str, Any] | None) -> str | None:
    if not context:
        return None

    value = context.get("document_id")
    if not isinstance(value, str):
        return None

    normalized = value.strip()
    return normalized or None


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
