from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from pliris.database.repositories.conversation_history import (
    ConversationHistoryRepository,
)


class FakeCursor:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def execute(self, query: str, params: tuple[Any, ...]) -> None:
        self.executed.append((query, params))

    def fetchall(self) -> list[dict[str, str]]:
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor


@pytest.mark.asyncio
async def test_history_reader_returns_chronological_bounded_messages() -> None:
    cursor = FakeCursor(
        [
            {"role": "assistant", "content": "Second"},
            {"role": "user", "content": "First"},
        ]
    )

    @contextmanager
    def connection_factory():
        yield FakeConnection(cursor)

    repository = ConversationHistoryRepository(connection_factory=connection_factory)

    messages = await repository.get_recent_messages(
        "v1.conversation.signature",
        limit=6,
    )

    assert messages == [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "Second"},
    ]
    assert cursor.executed[0][1] == (
        "v1.conversation.signature",
        6,
    )
