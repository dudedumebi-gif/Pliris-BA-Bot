from __future__ import annotations

from pathlib import Path

import pytest

from pliris.guardrails.scope_classifier import ScopeClassifier
from pliris.guardrails.scope_models import (
    ScopeCategory,
    ScopeDecision,
    ScopeIntent,
    ScopeOutcome,
)


class FakeRouter:
    def __init__(self, decision: ScopeDecision) -> None:
        self.decision = decision

    async def route(self, query: str) -> ScopeDecision:
        return self.decision


@pytest.mark.asyncio
async def test_classifier_preserves_semantic_in_scope_decision() -> None:
    classifier = ScopeClassifier(
        router=FakeRouter(
            ScopeDecision(
                outcome=ScopeOutcome.IN_SCOPE,
                category=ScopeCategory.BUSINESS_SYSTEMS_ANALYSIS,
                intent=ScopeIntent.ROLE_COMPARISON,
                confidence=0.93,
                rationale="The query compares BA and systems-analysis responsibilities.",
            )
        ),
        confidence_threshold=0.75,
    )

    result = await classifier.classify(
        "What differentiates a business analyst from a business systems analyst?"
    )

    assert result["in_scope"] is True
    assert result["category"] == "business_systems_analysis"
    assert result["intent"] == "role_comparison"
    assert result["router"] == "semantic_scope_agent"


@pytest.mark.asyncio
async def test_classifier_converts_low_confidence_to_clarification() -> None:
    classifier = ScopeClassifier(
        router=FakeRouter(
            ScopeDecision(
                outcome=ScopeOutcome.IN_SCOPE,
                category=ScopeCategory.BUSINESS_ANALYSIS,
                intent=ScopeIntent.OTHER_IN_SCOPE,
                confidence=0.51,
                rationale="The title may refer to several practices.",
            )
        ),
        confidence_threshold=0.75,
    )

    result = await classifier.classify("What does an analyst do?")

    assert result["in_scope"] is False
    assert result["category"] == "ambiguous"
    assert result["requires_clarification"] is True
    assert result["outcome"] == "clarification"


def test_classifier_contains_no_role_title_regex_catalogue() -> None:
    content = Path("pliris/guardrails/scope_classifier.py").read_text(encoding="utf-8")

    assert "re.compile" not in content
    assert "_BUSINESS_ANALYST" not in content
    assert "_BUSINESS_SYSTEMS_ANALYST" not in content
