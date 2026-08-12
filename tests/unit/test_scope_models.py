from pliris.guardrails.scope_models import (
    ScopeCategory,
    ScopeDecision,
    ScopeIntent,
    ScopeOutcome,
)


def test_scope_decision_accepts_consistent_in_scope_result() -> None:
    decision = ScopeDecision(
        outcome=ScopeOutcome.IN_SCOPE,
        category=ScopeCategory.BUSINESS_ANALYSIS,
        intent=ScopeIntent.PRACTICE_BOUNDARY,
        confidence=0.91,
        rationale="The question concerns whether a role belongs to BA practice.",
    )

    assert decision.category is ScopeCategory.BUSINESS_ANALYSIS
