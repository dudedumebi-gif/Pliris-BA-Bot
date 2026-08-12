from __future__ import annotations

from typing import Any

import pytest

from pliris.agents.scope_router import ScopeRouterAgent
from pliris.guardrails.scope_models import (
    ScopeCategory,
    ScopeDecision,
    ScopeIntent,
    ScopeOutcome,
)


class FakeStructuredClient:
    def __init__(self, decision: ScopeDecision) -> None:
        self.decision = decision
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ScopeDecision:
        self.calls.append(kwargs)
        return self.decision


@pytest.mark.asyncio
async def test_scope_router_uses_structured_semantic_policy() -> None:
    decision = ScopeDecision(
        outcome=ScopeOutcome.IN_SCOPE,
        category=ScopeCategory.BUSINESS_ANALYSIS,
        intent=ScopeIntent.PRACTICE_BOUNDARY,
        confidence=0.94,
        rationale="The query asks whether an organization-specific role overlaps BA.",
    )
    client = FakeStructuredClient(decision)
    router = ScopeRouterAgent(client=client, model="gpt-5-mini")

    result = await router.route(
        "Our company calls the role a solution analyst. Is it part of business analysis practice?"
    )

    assert result is decision
    call = client.calls[0]
    assert call["response_model"] is ScopeDecision
    assert call["model"] == "gpt-5-mini"
    assert "Do not rely on exact job-title matching" in call["system_prompt"]
    assert "organization-specific" in call["system_prompt"]
    assert "Missing facts needed to answer" in call["system_prompt"]


@pytest.mark.asyncio
async def test_scope_router_rejects_blank_query_before_model_call() -> None:
    decision = ScopeDecision(
        outcome=ScopeOutcome.OUT_OF_SCOPE,
        category=ScopeCategory.OUT_OF_SCOPE,
        intent=ScopeIntent.UNRELATED,
        confidence=1.0,
        rationale="Unused.",
    )
    client = FakeStructuredClient(decision)
    router = ScopeRouterAgent(client=client)

    with pytest.raises(ValueError, match="must not be blank"):
        await router.route("   ")

    assert client.calls == []
