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
            "reason": "The practice is not specified.",
            "requires_clarification": True,
            "outcome": "clarification",
            "router": "semantic_scope_agent",
        }


class MustNotRun:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"{name} must not run for clarification.")


@pytest.mark.asyncio
async def test_chat_returns_scope_clarification_without_grounded_call() -> None:
    response = await chat(
        request=ChatRequest(message="What does an analyst do?"),
        user={"id": "test-user", "name": "Test User"},
        orchestrator=MustNotRun(),
        scope_classifier=ClarificationScope(),
        request_classifier=MustNotRun(),
        prompt_injection_detector=FakeDetector(),
    )

    assert response.response == SCOPE_CLARIFICATION_RESPONSE
    assert response.citations == []
    assert response.metadata["guardrail"] == "scope_clarification"
    assert response.metadata["scope_decision"]["intent"] == "ambiguous"
