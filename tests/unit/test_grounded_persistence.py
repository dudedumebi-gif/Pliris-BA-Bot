from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from uuid import UUID

import pytest

from pliris.database.repositories.grounded_persistence import (
    GroundedExchange,
    GroundedPersistenceRepository,
)
from pliris.retrieval.models import RetrievedChunk

CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000101")
USER_MESSAGE_ID = UUID("00000000-0000-0000-0000-000000000102")
RETRIEVAL_QUERY_ID = UUID("00000000-0000-0000-0000-000000000103")
ASSISTANT_MESSAGE_ID = UUID("00000000-0000-0000-0000-000000000104")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000105")
CHUNK_ID = "00000000-0000-0000-0000-000000000201"


class FakeCursor:
    def __init__(
        self,
        *,
        existing_conversation: bool = False,
        fail_on: str | None = None,
    ) -> None:
        self.existing_conversation = existing_conversation
        self.fail_on = fail_on
        self.execute_calls: list[tuple[str, tuple[Any, ...] | None]] = []
        self.executemany_calls: list[tuple[str, list[tuple[Any, ...]]]] = []
        self._next_row: dict[str, Any] | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def execute(
        self,
        query: str,
        parameters: tuple[Any, ...] | None = None,
    ) -> None:
        normalized = " ".join(query.split()).lower()
        self.execute_calls.append((normalized, parameters))

        if self.fail_on and self.fail_on in normalized:
            raise RuntimeError("forced database failure")

        if normalized.startswith("select pg_advisory_xact_lock"):
            self._next_row = None
        elif "from public.conversations" in normalized and normalized.startswith("select id"):
            self._next_row = {"id": CONVERSATION_ID} if self.existing_conversation else None
        elif normalized.startswith("insert into public.conversations"):
            self._next_row = {"id": CONVERSATION_ID}
        elif normalized.startswith("insert into public.messages"):
            if "'user'" in normalized:
                self._next_row = {"id": USER_MESSAGE_ID}
            else:
                self._next_row = {"id": ASSISTANT_MESSAGE_ID}
        elif normalized.startswith("insert into public.retrieval_queries"):
            self._next_row = {"id": RETRIEVAL_QUERY_ID}
        elif normalized.startswith("insert into public.monitoring_events"):
            self._next_row = {"id": EVENT_ID}
        else:
            self._next_row = None

    def executemany(
        self,
        query: str,
        rows: list[tuple[Any, ...]],
    ) -> None:
        normalized = " ".join(query.split()).lower()
        self.executemany_calls.append((normalized, rows))

    def fetchone(self) -> dict[str, Any] | None:
        return self._next_row


class FakeConnection:
    def __init__(
        self,
        *,
        existing_conversation: bool = False,
        fail_on: str | None = None,
    ) -> None:
        self.cursor_instance = FakeCursor(
            existing_conversation=existing_conversation,
            fail_on=fail_on,
        )
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def connection_factory(
    connection: FakeConnection,
):
    @contextmanager
    def factory():
        yield connection

    return factory


def make_exchange(
    *,
    client_session_id: str | None = "session-1",
) -> GroundedExchange:
    chunk = RetrievedChunk(
        rank=1,
        chunk_id=CHUNK_ID,
        text="Requirements traceability records lineage.",
        title="BABOK Guide",
        source="babok-v3",
        page_start=87,
        page_end=91,
        score=0.038,
        document_id=("00000000-0000-0000-0000-000000000301"),
        metadata={
            "manifest_document_id": "babok-v3",
            "semantic_rank": 2,
            "keyword_rank": 1,
        },
    )
    return GroundedExchange(
        client_session_id=client_session_id,
        user_id="user-1",
        original_query="What is requirements traceability?",
        assistant_response="It records requirement lineage [S1].",
        scope_status="in_scope",
        scope_confidence=None,
        scope_category="business_analysis",
        citations=(
            {
                "citation_id": "S1",
                "chunk_id": CHUNK_ID,
                "source": "babok-v3",
            },
        ),
        model_name="gpt-5-mini-2025-08-07",
        input_tokens=100,
        output_tokens=25,
        total_latency_ms=1234.6,
        retrieval_latency_ms=234.4,
        requested_match_count=5,
        chunks=(chunk,),
        selected_chunk_ids=frozenset({CHUNK_ID}),
        insufficient_evidence=False,
        response_id="resp-1",
        metadata={
            "retrieved_count": 1,
            "confidence_basis": ("validated_citation_contract"),
        },
    )


@pytest.mark.asyncio
async def test_persist_exchange_writes_atomic_record_set() -> None:
    connection = FakeConnection()
    repository = GroundedPersistenceRepository(
        connection_factory=connection_factory(connection),
        json_wrapper=lambda value: value,
    )

    outcome = await repository.persist_exchange(make_exchange())

    assert connection.committed is True
    assert connection.rolled_back is False
    assert outcome.client_session_id == "session-1"
    assert outcome.database_conversation_id == str(CONVERSATION_ID)
    assert outcome.user_message_id == str(USER_MESSAGE_ID)
    assert outcome.assistant_message_id == str(ASSISTANT_MESSAGE_ID)
    assert outcome.retrieval_query_id == str(RETRIEVAL_QUERY_ID)
    assert outcome.monitoring_event_id == str(EVENT_ID)
    assert outcome.retrieval_result_count == 1

    cursor = connection.cursor_instance
    statements = [statement for statement, _ in cursor.execute_calls]
    assert any("insert into public.conversations" in statement for statement in statements)
    assert sum("insert into public.messages" in statement for statement in statements) == 2
    assert any("insert into public.retrieval_queries" in statement for statement in statements)
    assert any("insert into public.monitoring_events" in statement for statement in statements)

    _, result_rows = cursor.executemany_calls[0]
    assert result_rows == [
        (
            RETRIEVAL_QUERY_ID,
            CHUNK_ID,
            1,
            0.038,
            2,
            1,
            True,
        )
    ]

    monitoring_call = next(
        parameters
        for statement, parameters in cursor.execute_calls
        if "insert into public.monitoring_events" in statement
    )
    properties = monitoring_call[2]
    assert properties["scope_confidence"] == 1.0
    assert properties["scope_confidence_basis"] == ("validated_discrete_scope_decision")
    assert properties["cited_chunk_ids"] == [CHUNK_ID]


@pytest.mark.asyncio
async def test_persist_exchange_reuses_existing_session() -> None:
    connection = FakeConnection(existing_conversation=True)
    repository = GroundedPersistenceRepository(
        connection_factory=connection_factory(connection),
        json_wrapper=lambda value: value,
    )

    await repository.persist_exchange(make_exchange())

    statements = [statement for statement, _ in (connection.cursor_instance.execute_calls)]
    assert not any("insert into public.conversations" in statement for statement in statements)
    assert any(
        statement.startswith("update public.conversations set title") for statement in statements
    )


@pytest.mark.asyncio
async def test_persist_exchange_generates_session_id() -> None:
    connection = FakeConnection()
    repository = GroundedPersistenceRepository(
        connection_factory=connection_factory(connection),
        json_wrapper=lambda value: value,
    )

    outcome = await repository.persist_exchange(make_exchange(client_session_id=None))

    UUID(outcome.client_session_id)


@pytest.mark.asyncio
async def test_persist_exchange_rolls_back_on_failure() -> None:
    connection = FakeConnection(fail_on="insert into public.monitoring_events")
    repository = GroundedPersistenceRepository(
        connection_factory=connection_factory(connection),
        json_wrapper=lambda value: value,
    )

    with pytest.raises(
        RuntimeError,
        match="forced database failure",
    ):
        await repository.persist_exchange(make_exchange())

    assert connection.committed is False
    assert connection.rolled_back is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "original_query",
            "   ",
            "original_query must not be blank",
        ),
        (
            "assistant_response",
            "",
            "assistant_response must not be blank",
        ),
        (
            "scope_status",
            "unknown",
            "scope_status must be",
        ),
        (
            "requested_match_count",
            0,
            "requested_match_count must be positive",
        ),
        (
            "scope_confidence",
            1.5,
            "scope_confidence must be between",
        ),
    ],
)
async def test_persist_exchange_validates_contract(
    field: str,
    value: Any,
    message: str,
) -> None:
    connection = FakeConnection()
    repository = GroundedPersistenceRepository(
        connection_factory=connection_factory(connection),
        json_wrapper=lambda item: item,
    )
    exchange = make_exchange()
    values = {name: getattr(exchange, name) for name in exchange.__dataclass_fields__}
    values[field] = value

    with pytest.raises(ValueError, match=message):
        await repository.persist_exchange(GroundedExchange(**values))

    assert connection.cursor_instance.execute_calls == []
