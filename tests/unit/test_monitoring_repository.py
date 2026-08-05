from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from pliris.database.repositories.monitoring import MonitoringRepository


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.current: dict[str, Any] = {}

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> None:
        self.connection.executions.append((query, parameters))
        if self.connection.fail:
            raise RuntimeError("private database detail")
        self.current = self.connection.results.pop(0)

    def fetchone(self) -> dict[str, Any] | None:
        return self.current.get("one")

    def fetchall(self) -> list[dict[str, Any]]:
        return self.current.get("all", [])


class FakeConnection(AbstractContextManager["FakeConnection"]):
    def __init__(self, results: list[dict[str, Any]], *, fail: bool = False) -> None:
        self.results = list(results)
        self.fail = fail
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_record_event_inserts_bounded_properties_and_commits() -> None:
    event_id = uuid4()
    conversation_id = uuid4()
    message_id = uuid4()
    connection = FakeConnection([{"one": {"id": event_id}}])
    repository = MonitoringRepository(
        connection_factory=lambda: connection,
        json_wrapper=lambda value: value,
    )

    result = asyncio.run(
        repository.record_event(
            event_type="chat.request.completed",
            severity="info",
            properties={"latency_ms": 250, "request_mode": "qa"},
            conversation_id=conversation_id,
            message_id=str(message_id),
        )
    )

    assert result == str(event_id)
    assert connection.commits == 1
    assert connection.rollbacks == 0
    query, parameters = connection.executions[0]
    assert "insert into public.monitoring_events" in query.lower()
    assert parameters == (
        "chat.request.completed",
        conversation_id,
        UUID(str(message_id)),
        "info",
        {"latency_ms": 250, "request_mode": "qa"},
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"event_type": "Invalid Event"}, "event_type"),
        ({"event_type": "chat.completed", "severity": "fatal"}, "severity"),
        (
            {"event_type": "chat.completed", "properties": {"query": "private"}},
            "not allowed",
        ),
        (
            {"event_type": "chat.completed", "conversation_id": "not-a-uuid"},
            "conversation_id",
        ),
    ],
)
def test_record_event_rejects_invalid_or_sensitive_data(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    repository = MonitoringRepository(connection_factory=lambda: FakeConnection([]))

    with pytest.raises(ValueError, match=message):
        asyncio.run(repository.record_event(**kwargs))


def test_list_events_filters_and_redacts_legacy_private_properties() -> None:
    event_id = uuid4()
    row = {
        "id": event_id,
        "event_type": "grounded_response_completed",
        "severity": "info",
        "properties": {
            "latency_ms": 400,
            "user_id": "guest-private",
            "nested": {"session_id": "private", "result_count": 4},
        },
        "created_at": datetime(2026, 8, 5, tzinfo=UTC),
    }
    connection = FakeConnection([{"one": {"total": 1}}, {"all": [row]}])
    repository = MonitoringRepository(connection_factory=lambda: connection)

    items, total = asyncio.run(
        repository.list_events(
            limit=25,
            offset=5,
            since_hours=168,
            event_type="grounded_response_completed",
            severity="info",
        )
    )

    assert total == 1
    assert items[0]["properties"] == {
        "latency_ms": 400,
        "nested": {"result_count": 4},
    }
    assert "conversation_id" not in items[0]
    assert "message_id" not in items[0]
    assert connection.executions[-1][1] == (
        168,
        "grounded_response_completed",
        "info",
        25,
        5,
    )


def test_record_event_rolls_back_database_failures() -> None:
    connection = FakeConnection([], fail=True)
    repository = MonitoringRepository(
        connection_factory=lambda: connection,
        json_wrapper=lambda value: value,
    )

    with pytest.raises(RuntimeError, match="private database detail"):
        asyncio.run(repository.record_event(event_type="chat.failed"))

    assert connection.commits == 0
    assert connection.rollbacks == 1
