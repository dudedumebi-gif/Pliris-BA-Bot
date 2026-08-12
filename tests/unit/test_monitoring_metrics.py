from __future__ import annotations

import asyncio

from pliris.monitoring.dashboard_queries import DashboardQueries
from pliris.monitoring.metrics import MetricsCollector


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def get_dashboard(self, *, since_hours: int) -> dict:
        self.calls.append(since_hours)
        return {"since_hours": since_hours, "total_responses": 3}


def test_metrics_collector_delegates_to_repository() -> None:
    repository = FakeRepository()
    collector = MetricsCollector(repository=repository)  # type: ignore[arg-type]

    result = asyncio.run(collector.get_dashboard(since_hours=168))

    assert result == {"since_hours": 168, "total_responses": 3}
    assert repository.calls == [168]


def test_dashboard_bucket_selection_and_bounds() -> None:
    assert DashboardQueries.bucket_for_hours(24) == "hour"
    assert DashboardQueries.bucket_for_hours(48) == "hour"
    assert DashboardQueries.bucket_for_hours(168) == "day"
