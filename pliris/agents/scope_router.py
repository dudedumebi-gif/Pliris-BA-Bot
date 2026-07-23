from __future__ import annotations

import logging
from typing import Protocol

from pliris.config.settings import settings
from pliris.generation.openai_client import OpenAIClient
from pliris.generation.prompts import SCOPE_ROUTER_SYSTEM_PROMPT
from pliris.guardrails.scope_models import ScopeDecision

logger = logging.getLogger(__name__)


class StructuredScopeClient(Protocol):
    """Minimal structured-output client used by the Scope Router Agent."""

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ScopeDecision],
        model: str | None = None,
    ) -> ScopeDecision:
        """Return a validated structured scope decision."""


class ScopeRoutingError(RuntimeError):
    """Raised when semantic scope routing cannot produce a valid decision."""


class ScopeRouterAgent:
    """Semantic agent that routes by responsibilities and intent, not titles."""

    def __init__(
        self,
        *,
        client: StructuredScopeClient | None = None,
        model: str | None = None,
    ) -> None:
        self.client = client or OpenAIClient()
        self.model = model or settings.openai_chat_model

    async def route(self, query: str) -> ScopeDecision:
        """Return a structured semantic decision for one user query."""

        normalized = " ".join(query.split())
        if not normalized:
            raise ValueError("query must not be blank")

        try:
            return await self.client.generate_structured(
                system_prompt=SCOPE_ROUTER_SYSTEM_PROMPT,
                user_prompt=(f"Route this user query without answering it:\n\n{normalized}"),
                response_model=ScopeDecision,
                model=self.model,
            )
        except Exception as exc:
            logger.exception("Semantic scope routing failed")
            raise ScopeRoutingError("Unable to produce a valid semantic scope decision.") from exc
