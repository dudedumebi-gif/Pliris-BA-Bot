from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from pliris.monitoring.events import EventLogger


class FakeRepository:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    async def record_event(self, **values: Any) -> str:
        self.calls.append(values)
        if self.fail:
            raise RuntimeError("private database detail")
        return "event-1"

    async def get_events(
        self,
        event_type: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        return [{"event_type": event_type, "limit": limit}]


@pytest.mark.asyncio
async def test_event_logger_records_privacy_safe_operational_fields() -> None:
    repository = FakeRepository()
    event_logger = EventLogger(repository=repository)
    message_id = uuid4()

    result = await event_logger.log_feedback_submitted(
        message_id=message_id,
        rating=-1,
        has_comment=True,
        citation_answered=False,
        scope_answered=True,
    )

    assert result == "event-1"
    assert repository.calls == [
        {
            "event_type": "feedback.submitted",
            "severity": "info",
            "properties": {
                "rating": -1,
                "has_comment": True,
                "citation_answered": False,
                "scope_answered": True,
            },
            "conversation_id": None,
            "message_id": message_id,
        }
    ]


@pytest.mark.asyncio
async def test_event_logger_legacy_methods_drop_raw_content_and_identity() -> None:
    repository = FakeRepository()
    event_logger = EventLogger(repository=repository)

    await event_logger.log_query(
        "private query text",
        "guest-private",
        conversation_id="opaque-token",
        metadata={"prompt": "private"},
    )
    await event_logger.log_response(
        "private response text",
        "private-query-id",
        0.75,
        metadata={"content": "private"},
    )
    await event_logger.log_error(
        "Database Failure",
        "private exception message",
        metadata={"stack_trace": "private"},
    )

    serialized = repr(repository.calls)
    assert "private query text" not in serialized
    assert "private response text" not in serialized
    assert "guest-private" not in serialized
    assert "private-query-id" not in serialized
    assert "private exception message" not in serialized
    assert "stack_trace" not in serialized
    assert repository.calls[0]["properties"] == {
        "query_length": 18,
        "has_conversation": True,
    }
    assert repository.calls[2]["properties"]["error_type"] == "database_failure"


@pytest.mark.asyncio
async def test_event_logger_fails_open_when_monitoring_storage_is_unavailable() -> None:
    repository = FakeRepository(fail=True)
    event_logger = EventLogger(repository=repository)

    result = await event_logger.log_chat_failure(
        stage="chat_route",
        error_type="RuntimeError",
    )

    assert result is None
    assert len(repository.calls) == 1


@pytest.mark.asyncio
async def test_event_logger_preserves_protected_recent_event_compatibility() -> None:
    event_logger = EventLogger(repository=FakeRepository())

    result = await event_logger.get_recent_events(
        event_type="feedback.submitted",
        limit=25,
    )

    assert result == [{"event_type": "feedback.submitted", "limit": 25}]
