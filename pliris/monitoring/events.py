import logging

from pliris.database.repositories.monitoring import MonitoringRepository

logger = logging.getLogger(__name__)


class EventLogger:
    """Log application events for monitoring."""

    def __init__(self):
        self.repo = MonitoringRepository()

    async def log_query(
        self,
        query: str,
        user_id: str,
        conversation_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Log a query event."""
        event_data = {
            "event_type": "query",
            "query": query,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "metadata": metadata or {},
        }
        return await self.repo.log_event("query", event_data)

    async def log_response(
        self, response: str, query_id: str, confidence: float, metadata: dict | None = None
    ) -> str:
        """Log a response event."""
        event_data = {
            "event_type": "response",
            "response": response[:500],  # Truncate for storage
            "query_id": query_id,
            "confidence": confidence,
            "metadata": metadata or {},
        }
        return await self.repo.log_event("response", event_data)

    async def log_error(
        self, error_type: str, error_message: str, metadata: dict | None = None
    ) -> str:
        """Log an error event."""
        event_data = {
            "event_type": "error",
            "error_type": error_type,
            "error_message": error_message,
            "metadata": metadata or {},
        }
        return await self.repo.log_event("error", event_data)

    async def log_guardrail_trigger(
        self, guardrail_type: str, triggered: bool, metadata: dict | None = None
    ) -> str:
        """Log a guardrail trigger event."""
        event_data = {
            "event_type": "guardrail",
            "guardrail_type": guardrail_type,
            "triggered": triggered,
            "metadata": metadata or {},
        }
        return await self.repo.log_event("guardrail", event_data)

    async def get_recent_events(self, event_type: str | None = None, limit: int = 50) -> list[dict]:
        """Get recent events."""
        return await self.repo.get_events(event_type, limit)
