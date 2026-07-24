from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from pliris.database.repositories.documents import DocumentRepository


class FakeCursor:
    def __init__(
        self,
        *,
        fetchone_values: list[dict[str, Any] | None] | None = None,
        fetchall_values: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.executed: list[tuple[str, tuple[Any, ...] | None]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] | None = None,
    ) -> None:
        self.executed.append((sql, parameters))

    def fetchone(self) -> dict[str, Any] | None:
        return self.fetchone_values.pop(0)

    def fetchall(self) -> list[dict[str, Any]]:
        return self.fetchall_values.pop(0)


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> FakeCursor:
        return self._cursor


def _factory(cursor: FakeCursor):
    @contextmanager
    def connection_factory():
        yield FakeConnection(cursor)

    return connection_factory


def _summary_row() -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "id": uuid4(),
        "manifest_id": "babok-v3",
        "title": "BABOK Guide",
        "source_filename": "BABOK.pdf",
        "author": "IIBA",
        "source_type": "book",
        "access": "private",
        "status": "ready",
        "page_count": 500,
        "chunk_count": 42,
        "total_tokens": 20000,
        "last_ingested_at": now,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_list_documents_uses_filters_and_aggregate_counts() -> None:
    row = _summary_row()
    cursor = FakeCursor(
        fetchone_values=[{"total": 1}],
        fetchall_values=[[row]],
    )
    repository = DocumentRepository(
        connection_factory=_factory(cursor),
    )

    items, total = await repository.list_documents(
        limit=25,
        offset=5,
        status="ready",
        query="BABOK",
    )

    assert total == 1
    assert items == [row]

    count_sql, count_params = cursor.executed[0]
    list_sql, list_params = cursor.executed[1]

    assert "from public.documents" in count_sql
    assert "d.status = %s" in count_sql
    assert "ilike %s" in count_sql
    assert count_params == (
        "ready",
        "%BABOK%",
        "%BABOK%",
        "%BABOK%",
        "%BABOK%",
    )
    assert "public.document_chunks" in list_sql
    assert list_params[-2:] == (25, 5)


@pytest.mark.asyncio
async def test_get_document_excludes_storage_path_and_raw_error() -> None:
    row = {
        **_summary_row(),
        "edition": "Version 3",
        "publication_year": 2015,
        "mime_type": "application/pdf",
        "checksum_sha256": "a" * 64,
        "metadata": {
            "source_type": "book",
            "access": "private",
        },
        "has_ingestion_error": False,
    }
    cursor = FakeCursor(fetchone_values=[row])
    repository = DocumentRepository(
        connection_factory=_factory(cursor),
    )

    result = await repository.get_by_id(row["id"])

    assert result == row

    sql = cursor.executed[0][0]
    assert "storage_path" not in sql
    assert "ingestion_error," not in sql
    assert "has_ingestion_error" in sql


@pytest.mark.asyncio
async def test_list_chunks_is_paginated_and_ordered() -> None:
    document_id = uuid4()
    now = datetime.now(UTC)
    chunk = {
        "id": uuid4(),
        "chunk_index": 0,
        "content": "Grounded source content",
        "page_start": 1,
        "page_end": 1,
        "chapter": None,
        "section": "Introduction",
        "heading_path": ["Introduction"],
        "token_count": 20,
        "content_hash": "b" * 64,
        "embedding_model": "text-embedding-3-small",
        "created_at": now,
        "updated_at": now,
    }
    cursor = FakeCursor(
        fetchone_values=[{"total": 1}],
        fetchall_values=[[chunk]],
    )
    repository = DocumentRepository(
        connection_factory=_factory(cursor),
    )

    items, total = await repository.list_chunks(
        document_id,
        limit=10,
        offset=0,
    )

    assert total == 1
    assert items == [chunk]
    assert "order by chunk_index" in cursor.executed[1][0]
    assert cursor.executed[1][1] == (document_id, 10, 0)
