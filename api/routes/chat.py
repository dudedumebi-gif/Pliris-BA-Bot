import logging

from fastapi import APIRouter, Depends, HTTPException, status

from api.schemas.chat import ChatRequest, ChatResponse
from pliris.agents.orchestrator import AgentOrchestrator
from pliris.guardrails.prompt_injection import PromptInjectionDetector
from pliris.guardrails.scope_classifier import ScopeClassifier

logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = AgentOrchestrator()
scope_classifier = ScopeClassifier()
prompt_injection_detector = PromptInjectionDetector()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(
        lambda: {
            "id": "system",
            "name": "System User",
        }
    ),
):
    """
    Process a chat message and return a response with citations.

    This endpoint:
    1. Validates the request
    2. Checks for prompt injection
    3. Classifies the query scope
    4. Retrieves relevant documents
    5. Generates a response with citations
    6. Returns the response with metadata
    """
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
                "Query out of scope: %s",
                request.message,
            )

            out_of_scope_response = (
                "Pliris BA Bot is designed to assist with Business Analysis, "
                "Business Systems Analysis, and Project Management practices. "
                "Please ask a question related to one of these areas."
            )

            return ChatResponse(
                response=out_of_scope_response,
                citations=[],
                confidence=0.0,
                scope=scope_result["category"],
                conversation_id=request.conversation_id,
            )

        result = await orchestrator.process_query(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=user["id"],
        )

        return ChatResponse(
            response=result["response"],
            citations=result.get("citations", []),
            confidence=result.get("confidence", 0.0),
            scope=scope_result["category"],
            conversation_id=result.get("conversation_id"),
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
async def chat_stream(request: ChatRequest):
    """Stream a chat response when streaming support is implemented."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Streaming not yet implemented",
    )
