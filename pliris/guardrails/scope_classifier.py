from __future__ import annotations

from pliris.agents.scope_router import ScopeRouterAgent
from pliris.config.settings import settings
from pliris.guardrails.scope_models import (
    ScopeCategory,
    ScopeDecision,
    ScopeIntent,
    ScopeOutcome,
)


class ScopeClassifier:
    """Adapt the semantic Scope Router Agent to the chat pipeline contract."""

    def __init__(
        self,
        *,
        router: ScopeRouterAgent | None = None,
        confidence_threshold: float | None = None,
    ) -> None:
        self.router = router or ScopeRouterAgent()
        self.confidence_threshold = (
            settings.scope_confidence_threshold
            if confidence_threshold is None
            else confidence_threshold
        )
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0 and 1.")

    async def classify(self, query: str) -> dict[str, object]:
        """Return a policy-controlled semantic scope result."""

        decision = await self.router.route(query)
        effective = self._apply_confidence_policy(decision)

        return {
            "category": effective.category.value,
            "in_scope": effective.outcome is ScopeOutcome.IN_SCOPE,
            "confidence": effective.confidence,
            "intent": effective.intent.value,
            "reason": effective.rationale,
            "requires_clarification": (effective.outcome is ScopeOutcome.CLARIFICATION),
            "outcome": effective.outcome.value,
            "router": "semantic_scope_agent",
        }

    def _apply_confidence_policy(
        self,
        decision: ScopeDecision,
    ) -> ScopeDecision:
        """Convert low-confidence decisions into honest clarification."""

        if (
            decision.outcome is ScopeOutcome.CLARIFICATION
            or decision.confidence >= self.confidence_threshold
        ):
            return decision

        return ScopeDecision(
            outcome=ScopeOutcome.CLARIFICATION,
            category=ScopeCategory.AMBIGUOUS,
            intent=ScopeIntent.AMBIGUOUS,
            confidence=decision.confidence,
            rationale=(
                "The semantic router was not confident enough to apply "
                f"the proposed decision: {decision.rationale}"
            ),
        )
