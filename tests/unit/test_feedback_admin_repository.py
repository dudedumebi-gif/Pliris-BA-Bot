from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from pliris.database.repositories.feedback import FeedbackRepository


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
        self.current = self.connection.results.pop(0)

    def fetchone(self) -> dict[str, Any] | None:
        return self.current.get("one")

    def fetchall(self) -> list[dict[str, Any]]:
        return self.current.get("all", [])


class FakeConnection(AbstractContextManager["FakeConnection"]):
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = list(results)
        self.executions: list[tuple[str, tuple[Any, ...]]] = []
        self.rollbacks = 0

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def rollback(self) -> None:
        self.rollbacks += 1


def test_list_feedback_returns_context_without_session_identifiers() -> None:
    feedback_id = uuid4()
    assistant_id = uuid4()
    row = {
        "id": feedback_id,
        "assistant_message_id": assistant_id,
        "rating": 1,
        "citation_helpful": True,
        "scope_decision_correct": True,
        "comment": "Grounded and useful.",
        "user_message": "What is a stakeholder map?",
        "assistant_message": "A stakeholder map is...",
        "scope_status": "in_scope",
        "scope_confidence": 0.99,
        "citations": [{"document_id": "babok-v3"}],
        "model_name": "gpt-5-mini",
        "input_tokens": 50,
        "output_tokens": 75,
        "latency_ms": 800,
        "created_at": datetime(2026, 8, 5, tzinfo=UTC),
    }
    connection = FakeConnection([{"one": {"total": 1}}, {"all": [row]}])
    repository = FeedbackRepository(connection_factory=lambda: connection)

    items, total = asyncio.run(
        repository.list_feedback(
            limit=25,
            rating=1,
            citation_helpful=True,
            scope_decision_correct=True,
        )
    )

    assert total == 1
    assert items == [row]
    assert "conversation_id" not in items[0]
    assert "client_session_id" not in items[0]
    sql = " ".join(query for query, _ in connection.executions)
    assert "left join lateral" in sql.lower()
    assert connection.executions[-1][1] == (1, True, True, 25, 0)


def test_feedback_stats_returns_aggregate_counts() -> None:
    expected = {
        "total_feedback": 4,
        "helpful_feedback": 3,
        "unhelpful_feedback": 1,
        "commented_feedback": 2,
        "citation_ratings": 2,
        "citation_helpful": 1,
        "scope_ratings": 3,
        "scope_correct": 3,
        "latest_feedback_at": datetime(2026, 8, 5, tzinfo=UTC),
    }
    connection = FakeConnection([{"one": expected}])

    result = asyncio.run(
        FeedbackRepository(connection_factory=lambda: connection).get_stats()
    )

    assert result == expected
    assert "filter" in connection.executions[0][0].lower()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"offset": -1},
        {"rating": 0},
        {"citation_helpful": "yes"},
        {"scope_decision_correct": 1},
    ],
)
def test_list_feedback_validates_filters(kwargs: dict[str, Any]) -> None:
    repository = FeedbackRepository(connection_factory=lambda: FakeConnection([]))

    with pytest.raises(ValueError):
        asyncio.run(repository.list_feedback(**kwargs))
