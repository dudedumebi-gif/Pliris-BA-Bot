from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from api.conversation_tokens import ConversationTokenManager
from api.routes.chat import chat
from api.schemas.chat import ChatRequest
from pliris.agents.conversation_context import ConversationContextResolver
from pliris.agents.request_classifier import (
    RequestClassification,
    RequestMode,
)


class FakeDetector:
    def detect(self, message: str) -> bool:
        return False


class FakeScope:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def classify(self, message: str) -> dict[str, Any]:
        self.messages.append(message)
        return {
            "in_scope": True,
            "category": "business_analysis",
            "confidence": 0.9,
        }


class FakeRequestClassifier:
    def classify(self, message: str) -> RequestClassification:
        return RequestClassification(
            mode=RequestMode.GROUNDED_QUESTION,
            confidence=0.8,
            matched_rule="continuation_test",
        )


class FakeHistory:
    def __init__(self, messages: list[dict[str, str]]) -> None:
        self.messages = messages
        self.calls: list[str] = []

    async def get_recent_messages(
        self,
        conversation_id: str,
        *,
        limit: int,
    ) -> list[dict[str, str]]:
        self.calls.append(conversation_id)
        return self.messages[-limit:]


class FakeResult:
    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": "A traceability example [S1].",
            "citations": [
                {
                    "citation_id": "S1",
                    "chunk_id": "chunk-1",
                    "source": "babok-v3",
                    "title": "BABOK",
                    "text": "Traceability example.",
                    "page": 1,
                    "page_start": 1,
                    "page_end": 1,
                    "score": 0.1,
                    "rank": 1,
                    "document_id": "doc-1",
                    "metadata": {},
                }
            ],
            "confidence": 1.0,
            "insufficient_evidence": False,
            "conversation_id": self.conversation_id,
            "model": "gpt-5-mini",
            "response_id": "resp-1",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
            },
            "metadata": {"persistence": {"status": "completed"}},
        }


class FakeOrchestrator:
    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.calls: list[dict[str, Any]] = []

    async def process_query(self, **kwargs: Any) -> FakeResult:
        self.calls.append(kwargs)
        return FakeResult(self.conversation_id)


@pytest.mark.asyncio
async def test_chat_resolves_owned_context_dependent_follow_up() -> None:
    session_id = str(uuid4())
    tokens = ConversationTokenManager("test-secret")
    token = tokens.issue(session_id)
    history = FakeHistory(
        [
            {
                "role": "user",
                "content": "What is requirements traceability?",
            },
            {
                "role": "assistant",
                "content": "Traceability links requirements [S1].",
            },
        ]
    )
    scope = FakeScope()
    orchestrator = FakeOrchestrator(token)

    response = await chat(
        request=ChatRequest(
            message=("Give me a practical example based on the explanation you just provided."),
            conversation_id=token,
        ),
        user={
            "id": "guest-test",
            "name": "Guest User",
            "session_id": session_id,
        },
        orchestrator=orchestrator,
        scope_classifier=scope,
        request_classifier=FakeRequestClassifier(),
        prompt_injection_detector=FakeDetector(),
        conversation_tokens=tokens,
        conversation_history=history,
        context_resolver=ConversationContextResolver(),
    )

    assert response.conversation_id == token
    assert response.metadata["conversation_context"] == {
        "context_used": True,
        "history_message_count": 2,
    }
    assert "requirements traceability" in scope.messages[0]
    call = orchestrator.calls[0]
    assert call["message"].startswith("Give me a practical example")
    assert "Previous Business Analysis" in call["retrieval_query"]
    assert "Previous question" in call["generation_question"]


@pytest.mark.asyncio
async def test_chat_rejects_conversation_token_from_another_session() -> None:
    tokens = ConversationTokenManager("test-secret")
    token = tokens.issue(str(uuid4()))
    scope = FakeScope()

    with pytest.raises(HTTPException) as error:
        await chat(
            request=ChatRequest(
                message="Explain that in more detail.",
                conversation_id=token,
            ),
            user={
                "id": "guest-other",
                "name": "Guest User",
                "session_id": str(uuid4()),
            },
            orchestrator=FakeOrchestrator(token),
            scope_classifier=scope,
            request_classifier=FakeRequestClassifier(),
            prompt_injection_detector=FakeDetector(),
            conversation_tokens=tokens,
            conversation_history=FakeHistory([]),
            context_resolver=ConversationContextResolver(),
        )

    assert error.value.status_code == 403
    assert scope.messages == []


@pytest.mark.asyncio
async def test_chat_issues_bound_token_for_new_grounded_session() -> None:
    session_id = str(uuid4())
    tokens = ConversationTokenManager("test-secret")

    class EchoConversationOrchestrator(FakeOrchestrator):
        async def process_query(self, **kwargs: Any) -> FakeResult:
            self.calls.append(kwargs)
            return FakeResult(kwargs["conversation_id"])

    orchestrator = EchoConversationOrchestrator("unused")

    response = await chat(
        request=ChatRequest(message="What is requirements traceability?"),
        user={
            "id": "guest-test",
            "name": "Guest User",
            "session_id": session_id,
        },
        orchestrator=orchestrator,
        scope_classifier=FakeScope(),
        request_classifier=FakeRequestClassifier(),
        prompt_injection_detector=FakeDetector(),
        conversation_tokens=tokens,
        conversation_history=FakeHistory([]),
        context_resolver=ConversationContextResolver(),
    )

    assert response.conversation_id is not None
    assert tokens.validate(response.conversation_id, session_id) == (response.conversation_id)


@pytest.mark.asyncio
async def test_chat_resolves_scope_clarification_reply_as_one_request() -> None:
    session_id = str(uuid4())
    tokens = ConversationTokenManager("test-secret")
    token = tokens.issue(session_id)
    history = FakeHistory(
        [
            {"role": "user", "content": "What does an analyst do?"},
            {
                "role": "assistant",
                "content": "Please clarify the practice.",
                "scope_status": "borderline",
            },
        ]
    )
    scope = FakeScope()
    orchestrator = FakeOrchestrator(token)

    response = await chat(
        request=ChatRequest(
            message="I'm talking about a financial business analyst.",
            conversation_id=token,
        ),
        user={
            "id": "guest-test",
            "name": "Guest User",
            "session_id": session_id,
        },
        orchestrator=orchestrator,
        scope_classifier=scope,
        request_classifier=FakeRequestClassifier(),
        prompt_injection_detector=FakeDetector(),
        conversation_tokens=tokens,
        conversation_history=history,
        context_resolver=ConversationContextResolver(),
    )

    assert response.metadata["conversation_context"]["context_used"] is True
    assert "What does an analyst do?" in scope.messages[0]
    assert "financial business analyst" in scope.messages[0]
    call = orchestrator.calls[0]
    assert "What does an analyst do?" in call["retrieval_query"]
    assert "financial business analyst" in call["retrieval_query"]
