from __future__ import annotations

import logging
import re
from typing import Any
from uuid import UUID

from pliris.database.repositories.monitoring import MonitoringRepository

logger = logging.getLogger(__name__)

_SAFE_LABEL_PATTERN = re.compile(r"[^a-z0-9_.-]+")


class EventLogger:
    """Record privacy-safe operational events without breaking user flows."""

    def __init__(self, repository: MonitoringRepository | None = None) -> None:
        self.repo = repository or MonitoringRepository()

    async def record(
        self,
        *,
        event_type: str,
        severity: str = "info",
        properties: dict[str, Any] | None = None,
        conversation_id: str | UUID | None = None,
        message_id: str | UUID | None = None,
    ) -> str | None:
        """Best-effort write: monitoring must not break the primary request."""

        try:
            return await self.repo.record_event(
                event_type=event_type,
                severity=severity,
                properties=properties,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        except Exception:
            logger.warning(
                "Operational event could not be persisted: %s",
                event_type,
                exc_info=True,
            )
            return None

    async def log_prompt_injection(self, *, message_length: int) -> str | None:
        return await self.record(
            event_type="chat.prompt_injection_blocked",
            severity="warning",
            properties={"message_length": max(0, message_length)},
        )

    async def log_scope_decision(
        self,
        *,
        decision: str,
        category: str,
        confidence: float | None,
    ) -> str | None:
        properties: dict[str, Any] = {
            "decision": _safe_label(decision),
            "category": _safe_label(category),
        }
        if confidence is not None:
            properties["confidence"] = confidence
        return await self.record(
            event_type="chat.scope_decided",
            properties=properties,
        )

    async def log_chat_failure(self, *, stage: str, error_type: str) -> str | None:
        return await self.record(
            event_type="chat.request_failed",
            severity="error",
            properties={
                "stage": _safe_label(stage),
                "error_type": _safe_label(error_type),
            },
        )

    async def log_feedback_submitted(
        self,
        *,
        message_id: str | UUID,
        rating: int,
        has_comment: bool,
        citation_answered: bool,
        scope_answered: bool,
    ) -> str | None:
        return await self.record(
            event_type="feedback.submitted",
            properties={
                "rating": rating,
                "has_comment": has_comment,
                "citation_answered": citation_answered,
                "scope_answered": scope_answered,
            },
            message_id=message_id,
        )

    async def log_feedback_failure(
        self,
        *,
        reason: str,
        message_id: str | UUID | None = None,
    ) -> str | None:
        return await self.record(
            event_type="feedback.submission_failed",
            severity="warning",
            properties={"reason": _safe_label(reason)},
            message_id=message_id,
        )

    async def log_query(
        self,
        query: str,
        user_id: str,
        conversation_id: str | None = None,
        metadata: dict | None = None,
    ) -> str | None:
        """Compatibility shim that records no raw query or identity."""

        del user_id, metadata
        return await self.record(
            event_type="chat.query_received",
            properties={
                "query_length": len(query),
                "has_conversation": bool(conversation_id),
            },
        )

    async def log_response(
        self,
        response: str,
        query_id: str,
        confidence: float,
        metadata: dict | None = None,
    ) -> str | None:
        """Compatibility shim that records no raw response or query ID."""

        del query_id, metadata
        return await self.record(
            event_type="chat.response_completed",
            properties={
                "response_length": len(response),
                "confidence": confidence,
            },
        )

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        metadata: dict | None = None,
    ) -> str | None:
        """Compatibility shim that records no exception message."""

        del error_message, metadata
        return await self.log_chat_failure(
            stage="legacy_event_logger",
            error_type=error_type,
        )

    async def log_guardrail_trigger(
        self,
        guardrail_type: str,
        triggered: bool,
        metadata: dict | None = None,
    ) -> str | None:
        """Compatibility shim for existing guardrail producers."""

        del metadata
        return await self.record(
            event_type="chat.guardrail_evaluated",
            properties={
                "guardrail_type": _safe_label(guardrail_type),
                "triggered": triggered,
            },
        )

    async def get_recent_events(
        self,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return recent privacy-safe events for protected consumers."""

        return await self.repo.get_events(event_type, limit)


def _safe_label(value: object) -> str:
    normalized = _SAFE_LABEL_PATTERN.sub("_", str(value).strip().lower()).strip("_")
    return (normalized or "unknown")[:64]
