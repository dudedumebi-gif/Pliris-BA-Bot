from __future__ import annotations

from pliris.database.repositories.monitoring import MonitoringRepository


class MetricsCollector:
    """Collect truthful, aggregate-only dashboard metrics."""

    def __init__(self, repository: MonitoringRepository | None = None) -> None:
        self.repository = repository or MonitoringRepository()

    async def get_dashboard(self, *, since_hours: int = 24) -> dict:
        """Return one bounded dashboard snapshot from persisted operational data."""

        return await self.repository.get_dashboard(since_hours=since_hours)
