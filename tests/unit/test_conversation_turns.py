from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from pliris.database.repositories.conversation_turns import (
    ConversationTurnRepository,
)


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.fetches = [None, {"id": "conversation-1"}]

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed.append((sql, params))

    def fetchone(self) -> dict[str, str] | None:
        return self.fetches.pop(0)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.asyncio
async def test_persist_turn_writes_user_and_assistant_messages() -> None:
    cursor = FakeCursor()
    connection = FakeConnection(cursor)

    @contextmanager
    def factory() -> Any:
        yield connection

    repository = ConversationTurnRepository(
        connection_factory=factory,
    )

    await repository.persist_turn(
        client_session_id="session-1",
        user_message="What does an analyst do?",
        assistant_message="Please clarify the practice.",
        scope_status="borderline",
        scope_confidence=0.44,
    )

    assert connection.committed is True
    sql = "\n".join(statement for statement, _ in cursor.executed)
    assert "insert into public.conversations" in sql
    assert sql.count("insert into public.messages") == 2
