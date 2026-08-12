from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from pliris.database.repositories.source_lifecycle import (
    SourceConfirmationError,
    SourceLifecycleConflictError,
    SourceLifecycleRepository,
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

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def _factory(cursor: FakeCursor):
    @contextmanager
    def connection_factory():
        yield FakeConnection(cursor)

    return connection_factory


def _event(document_id, action: str) -> dict[str, Any]:
    previous = "ready" if action == "archive" else "archived"
    new = "archived" if action == "archive" else "ready"
    return {
        "id": uuid4(),
        "document_id": document_id,
        "action": action,
        "actor": "developer-api",
        "reason": "Lifecycle acceptance test.",
        "previous_status": previous,
        "new_status": new,
        "metadata": {},
        "created_at": datetime.now(UTC),
    }


@pytest.mark.asyncio
async def test_archive_updates_status_and_creates_event_atomically() -> None:
    document_id = uuid4()
    event = _event(document_id, "archive")
    cursor = FakeCursor(
        [
            {
                "id": document_id,
                "manifest_id": "gao-agile-assessment-guide-2023",
                "title": "GAO Agile Assessment Guide",
                "status": "ready",
            },
            event,
        ]
    )
    repository = SourceLifecycleRepository(
        connection_factory=_factory(cursor),
    )

    result = await repository.archive(
        document_id,
        reason="Lifecycle acceptance test.",
        confirmation="gao-agile-assessment-guide-2023",
    )

    assert result == event
    assert "for update" in cursor.executed[0][0].lower()
    assert cursor.executed[1][1] == ("archived", document_id)
    assert "source_admin_events" in cursor.executed[2][0]


@pytest.mark.asyncio
async def test_archive_rejects_wrong_confirmation_before_update() -> None:
    document_id = uuid4()
    cursor = FakeCursor(
        [
            {
                "id": document_id,
                "manifest_id": "gao-agile-assessment-guide-2023",
                "title": "GAO Agile Assessment Guide",
                "status": "ready",
            }
        ]
    )
    repository = SourceLifecycleRepository(
        connection_factory=_factory(cursor),
    )

    with pytest.raises(SourceConfirmationError):
        await repository.archive(
            document_id,
            reason="Lifecycle acceptance test.",
            confirmation="babok-v3",
        )

    assert len(cursor.executed) == 1


@pytest.mark.asyncio
async def test_restore_requires_all_chunks_to_be_embedded() -> None:
    document_id = uuid4()
    cursor = FakeCursor(
        [
            {
                "id": document_id,
                "manifest_id": "gao-agile-assessment-guide-2023",
                "title": "GAO Agile Assessment Guide",
                "status": "archived",
            },
            {"chunk_count": 204, "embedded_chunk_count": 203},
        ]
    )
    repository = SourceLifecycleRepository(
        connection_factory=_factory(cursor),
    )

    with pytest.raises(SourceLifecycleConflictError):
        await repository.restore(
            document_id,
            reason="Restore after lifecycle acceptance.",
            confirmation="gao-agile-assessment-guide-2023",
        )

    assert len(cursor.executed) == 2


@pytest.mark.asyncio
async def test_missing_audit_result_fails_inside_transaction() -> None:
    document_id = uuid4()
    cursor = FakeCursor(
        [
            {
                "id": document_id,
                "manifest_id": "gao-agile-assessment-guide-2023",
                "title": "GAO Agile Assessment Guide",
                "status": "ready",
            },
            None,
        ]
    )
    repository = SourceLifecycleRepository(
        connection_factory=_factory(cursor),
    )

    with pytest.raises(
        RuntimeError,
        match="Lifecycle audit event was not created",
    ):
        await repository.archive(
            document_id,
            reason="Lifecycle acceptance test.",
            confirmation="gao-agile-assessment-guide-2023",
        )

    assert "update public.documents" in cursor.executed[1][0]
    assert "source_admin_events" in cursor.executed[2][0]
