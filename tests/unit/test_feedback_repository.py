from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from pliris.database.repositories.feedback import (
    FeedbackRepository,
    FeedbackTargetNotFoundError,
)


class FakeCursor:
    def __init__(self, values: list[dict[str, Any] | None]) -> None:
        self.values = list(values)
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | None = None,
    ) -> None:
        self.executed.append((sql, parameters))

    def fetchone(self):
        return self.values.pop(0)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _factory(cursor: FakeCursor):
    connection = FakeConnection(cursor)

    @contextmanager
    def connection_factory():
        yield connection

    return connection_factory, connection


def _feedback(assistant_message_id: UUID) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "assistant_message_id": assistant_message_id,
        "rating": 1,
        "citation_helpful": True,
        "scope_decision_correct": None,
        "comment": "Useful answer.",
        "created_at": datetime.now(UTC),
    }


@pytest.mark.asyncio
async def test_upsert_verifies_ownership_and_uses_unique_message_key() -> None:
    conversation_id = uuid4()
    assistant_message_id = uuid4()
    feedback = _feedback(assistant_message_id)
    cursor = FakeCursor([{"conversation_id": conversation_id}, feedback])
    factory, connection = _factory(cursor)
    repository = FeedbackRepository(connection_factory=factory)

    result = await repository.upsert(
        client_session_id="v1.owned.signature",
        assistant_message_id=assistant_message_id,
        rating=1,
        citation_helpful=True,
        comment="  Useful answer.  ",
    )

    assert result == feedback
    assert "m.role = 'assistant'" in cursor.executed[0][0]
    assert "c.client_session_id = %s" in cursor.executed[0][0]
    assert "for update" in cursor.executed[0][0].lower()
    assert "on conflict (assistant_message_id)" in cursor.executed[1][0].lower()
    assert cursor.executed[1][1] == (
        conversation_id,
        assistant_message_id,
        1,
        True,
        None,
        "Useful answer.",
    )
    assert connection.commits == 1
    assert connection.rollbacks == 0


@pytest.mark.asyncio
async def test_upsert_rejects_message_outside_owned_conversation() -> None:
    cursor = FakeCursor([None])
    factory, connection = _factory(cursor)
    repository = FeedbackRepository(connection_factory=factory)

    with pytest.raises(FeedbackTargetNotFoundError):
        await repository.upsert(
            client_session_id="v1.owned.signature",
            assistant_message_id=uuid4(),
            rating=-1,
        )

    assert len(cursor.executed) == 1
    assert connection.commits == 0
    assert connection.rollbacks == 1


@pytest.mark.asyncio
async def test_upsert_rejects_invalid_values_before_database_access() -> None:
    def unused_factory():
        raise AssertionError("database must not be accessed")

    repository = FeedbackRepository(connection_factory=unused_factory)

    with pytest.raises(ValueError, match="rating"):
        await repository.upsert(
            client_session_id="v1.owned.signature",
            assistant_message_id=uuid4(),
            rating=0,
        )
