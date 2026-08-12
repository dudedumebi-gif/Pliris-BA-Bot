from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from psycopg.types.json import Jsonb

from ingestion.models import DocumentManifestEntry
from ingestion.repository import IngestionRepository


def _database_mocks() -> tuple[MagicMock, MagicMock, MagicMock]:
    connection_context = MagicMock()
    connection = connection_context.__enter__.return_value
    cursor = connection.cursor.return_value.__enter__.return_value
    return connection_context, connection, cursor


def test_get_document_by_checksum_returns_existing_document() -> None:
    connection_context, _, cursor = _database_mocks()
    existing = {
        "id": uuid4(),
        "manifest_id": "existing-guide",
        "title": "Existing Guide",
        "source_filename": "existing-guide.pdf",
        "checksum_sha256": "a" * 64,
        "status": "ready",
        "storage_path": "existing-guide/existing-guide.pdf",
    }
    cursor.fetchone.return_value = existing

    with patch(
        "ingestion.repository.postgres_connection",
        return_value=connection_context,
    ):
        result = IngestionRepository().get_document_by_checksum("a" * 64)

    assert result == existing
    sql, parameters = cursor.execute.call_args.args
    assert "where checksum_sha256 = %s" in sql
    assert parameters == ("a" * 64,)


def test_create_pending_document_is_insert_only_and_unprocessed() -> None:
    connection_context, connection, cursor = _database_mocks()
    database_document_id = uuid4()
    cursor.fetchone.return_value = {"id": database_document_id}
    manifest = DocumentManifestEntry(
        document_id="new-guide",
        title="New Guide",
        source_filename="new-guide.pdf",
        author="Example Author",
        publication_year=2026,
        metadata={"topic": "business-analysis"},
    )

    with patch(
        "ingestion.repository.postgres_connection",
        return_value=connection_context,
    ):
        result = IngestionRepository().create_pending_document(
            manifest=manifest,
            checksum_sha256="b" * 64,
            size_bytes=2048,
            storage_bucket="knowledge-base",
            storage_path="new-guide/new-guide.pdf",
        )

    assert result == database_document_id
    sql, parameters = cursor.execute.call_args.args
    normalized_sql = " ".join(sql.split())
    assert "insert into public.documents" in normalized_sql
    assert "'pending'" in normalized_sql
    assert "on conflict" not in normalized_sql
    assert parameters[:9] == (
        "new-guide",
        "New Guide",
        "new-guide.pdf",
        "knowledge-base",
        "new-guide/new-guide.pdf",
        "Example Author",
        None,
        2026,
        "b" * 64,
    )
    assert isinstance(parameters[9], Jsonb)
    assert parameters[9].obj["upload_size_bytes"] == 2048
    connection.commit.assert_called_once_with()


def test_claim_pending_document_uses_all_atomic_handoff_guards() -> None:
    connection_context, connection, cursor = _database_mocks()
    database_document_id = uuid4()
    cursor.fetchone.return_value = {"id": database_document_id}

    manifest = DocumentManifestEntry(
        document_id="staged-guide",
        title="Staged Guide",
        source_filename="staged-guide.pdf",
        author="Example Author",
        publication_year=2026,
        metadata={"topic": "business-analysis"},
    )

    with patch(
        "ingestion.repository.postgres_connection",
        return_value=connection_context,
    ):
        result = IngestionRepository().claim_pending_document(
            database_document_id=database_document_id,
            manifest=manifest,
            checksum_sha256="c" * 64,
            page_count=25,
            storage_bucket="knowledge-base",
            storage_path="staged-guide/staged-guide.pdf",
            pdf_metadata={"producer": "pytest"},
        )

    assert result == database_document_id

    sql, parameters = cursor.execute.call_args.args
    normalized_sql = " ".join(sql.split())

    assert "update public.documents" in normalized_sql
    assert "status = 'processing'" in normalized_sql
    assert "metadata = metadata || %s" in normalized_sql
    assert "where id = %s" in normalized_sql
    assert "and manifest_id = %s" in normalized_sql
    assert "and checksum_sha256 = %s" in normalized_sql
    assert "and storage_bucket = %s" in normalized_sql
    assert "and storage_path = %s" in normalized_sql
    assert "and status = 'pending'" in normalized_sql
    assert "not exists" in normalized_sql
    assert "from public.document_chunks" in normalized_sql
    assert "returning id" in normalized_sql

    assert parameters[:6] == (
        "Staged Guide",
        "staged-guide.pdf",
        "Example Author",
        None,
        2026,
        25,
    )
    assert isinstance(parameters[6], Jsonb)
    assert parameters[6].obj["pdf_metadata"] == {"producer": "pytest"}
    assert parameters[7:] == (
        database_document_id,
        "staged-guide",
        "c" * 64,
        "knowledge-base",
        "staged-guide/staged-guide.pdf",
    )

    connection.commit.assert_called_once_with()
    connection.rollback.assert_not_called()


def test_claim_pending_document_fails_closed_when_any_guard_misses() -> None:
    connection_context, connection, cursor = _database_mocks()
    cursor.fetchone.return_value = None

    manifest = DocumentManifestEntry(
        document_id="staged-guide",
        title="Staged Guide",
        source_filename="staged-guide.pdf",
    )

    with (
        patch(
            "ingestion.repository.postgres_connection",
            return_value=connection_context,
        ),
        pytest.raises(
            ValueError,
            match="identity, storage, state, or chunk guards did not match",
        ),
    ):
        IngestionRepository().claim_pending_document(
            database_document_id=uuid4(),
            manifest=manifest,
            checksum_sha256="d" * 64,
            page_count=25,
            storage_bucket="knowledge-base",
            storage_path="staged-guide/staged-guide.pdf",
            pdf_metadata={},
        )

    connection.rollback.assert_called_once_with()
    connection.commit.assert_not_called()
