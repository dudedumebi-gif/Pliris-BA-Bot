from __future__ import annotations

from typing import Any

import pytest

from api.routes.chat import SCOPE_CLARIFICATION_RESPONSE, chat
from api.schemas.chat import ChatRequest


class FakeDetector:
    def detect(self, message: str) -> bool:
        return False


class ClarificationScope:
    async def classify(self, query: str) -> dict[str, object]:
        return {
            "category": "ambiguous",
            "in_scope": False,
            "confidence": 0.44,
            "intent": "ambiguous",
            "reason": "The practice is unspecified.",
            "requires_clarification": True,
            "outcome": "clarification",
            "router": "semantic_scope_agent",
        }


class FakeTokenManager:
    def issue(self, session_id: str) -> str:
        assert session_id == "session-1"
        return "signed-conversation-token"


class FakeTurnRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def persist_turn(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class MustNotRun:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"{name} must not run for clarification.")


@pytest.mark.asyncio
async def test_clarification_issues_token_and_persists_turn() -> None:
    turns = FakeTurnRepository()

    response = await chat(
        request=ChatRequest(message="What does an analyst do?"),
        user={
            "id": "guest-1",
            "name": "Guest",
            "session_id": "session-1",
        },
        orchestrator=MustNotRun(),
        scope_classifier=ClarificationScope(),
        request_classifier=MustNotRun(),
        prompt_injection_detector=FakeDetector(),
        conversation_tokens=FakeTokenManager(),
        conversation_turns=turns,
    )

    assert response.response == SCOPE_CLARIFICATION_RESPONSE
    assert response.conversation_id == "signed-conversation-token"
    assert turns.calls == [
        {
            "client_session_id": "signed-conversation-token",
            "user_message": "What does an analyst do?",
            "assistant_message": SCOPE_CLARIFICATION_RESPONSE,
            "scope_status": "borderline",
            "scope_confidence": 0.44,
        }
    ]
