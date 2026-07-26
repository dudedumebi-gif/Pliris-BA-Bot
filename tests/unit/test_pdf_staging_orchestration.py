from __future__ import annotations

import hashlib
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ingestion.models import DocumentManifestEntry
from ingestion.staging import (
    PdfStagingConflictError,
    PdfStagingProtectedSourceError,
    PdfStagingValidationError,
    stage_pdf_upload,
)


def _manifest(
    *,
    document_id: str = "new-guide",
    source_filename: str = "new-guide.pdf",
) -> DocumentManifestEntry:
    return DocumentManifestEntry(
        document_id=document_id,
        title="New Guide",
        source_filename=source_filename,
        publication_year=2026,
        metadata={"topic": "business-analysis"},
    )


def _dependencies() -> tuple[MagicMock, MagicMock]:
    repository = MagicMock()
    repository.get_document_by_checksum.return_value = None
    repository.get_document.return_value = None

    storage = MagicMock()
    storage.bucket = "knowledge-base"
    storage.upload_pdf_bytes.return_value = "new-guide/new-guide.pdf"

    return repository, storage


def test_stage_pdf_upload_creates_pending_document() -> None:
    payload = b"%PDF-1.7\nvalidated-pdf-content"
    checksum = hashlib.sha256(payload).hexdigest()
    database_document_id = uuid4()
    manifest = _manifest()
    repository, storage = _dependencies()
    repository.create_pending_document.return_value = database_document_id

    result = stage_pdf_upload(
        manifest=manifest,
        filename="../incoming/new-guide.pdf",
        content_type="application/pdf",
        payload=payload,
        max_bytes=1024,
        repository=repository,
        storage=storage,
    )

    assert result.database_document_id == database_document_id
    assert result.manifest_id == "new-guide"
    assert result.safe_filename == "new-guide.pdf"
    assert result.checksum_sha256 == checksum
    assert result.size_bytes == len(payload)
    assert result.storage_bucket == "knowledge-base"
    assert result.storage_path == "new-guide/new-guide.pdf"
    assert result.status == "pending"

    repository.get_document_by_checksum.assert_called_once_with(checksum)
    repository.get_document.assert_called_once_with("new-guide")
    storage.upload_pdf_bytes.assert_called_once_with(
        payload,
        document_id="new-guide",
        filename="new-guide.pdf",
    )
    repository.create_pending_document.assert_called_once_with(
        manifest=manifest,
        checksum_sha256=checksum,
        size_bytes=len(payload),
        storage_bucket="knowledge-base",
        storage_path="new-guide/new-guide.pdf",
    )
    storage.remove.assert_not_called()


def test_stage_pdf_upload_rejects_duplicate_checksum_before_manifest_lookup() -> None:
    payload = b"%PDF-1.7\nduplicate-content"
    repository, storage = _dependencies()
    repository.get_document_by_checksum.return_value = {
        "manifest_id": "existing-guide",
        "status": "ready",
    }

    with pytest.raises(PdfStagingConflictError, match="checksum"):
        stage_pdf_upload(
            manifest=_manifest(),
            filename="new-guide.pdf",
            content_type="application/pdf",
            payload=payload,
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    repository.get_document.assert_not_called()
    storage.upload_pdf_bytes.assert_not_called()
    repository.create_pending_document.assert_not_called()


def test_stage_pdf_upload_rejects_manifest_id_collision_before_upload() -> None:
    repository, storage = _dependencies()
    repository.get_document.return_value = {
        "manifest_id": "new-guide",
        "status": "archived",
    }

    with pytest.raises(PdfStagingConflictError, match="manifest ID"):
        stage_pdf_upload(
            manifest=_manifest(),
            filename="new-guide.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nnew-content",
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    storage.upload_pdf_bytes.assert_not_called()
    repository.create_pending_document.assert_not_called()


def test_stage_pdf_upload_rejects_protected_babok_source() -> None:
    repository, storage = _dependencies()

    with pytest.raises(PdfStagingProtectedSourceError, match="protected"):
        stage_pdf_upload(
            manifest=_manifest(
                document_id="babok-v3",
                source_filename="BABOK_Guide_v3_Member.pdf",
            ),
            filename="BABOK_Guide_v3_Member.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nprotected-content",
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    repository.get_document_by_checksum.assert_not_called()
    repository.get_document.assert_not_called()
    storage.upload_pdf_bytes.assert_not_called()


def test_stage_pdf_upload_rejects_manifest_filename_mismatch() -> None:
    repository, storage = _dependencies()

    with pytest.raises(PdfStagingValidationError, match="manifest filename"):
        stage_pdf_upload(
            manifest=_manifest(),
            filename="different-guide.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nnew-content",
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    repository.get_document_by_checksum.assert_not_called()
    repository.get_document.assert_not_called()
    storage.upload_pdf_bytes.assert_not_called()


def test_stage_pdf_upload_stops_when_storage_upload_fails() -> None:
    repository, storage = _dependencies()
    storage.upload_pdf_bytes.side_effect = RuntimeError("storage unavailable")

    with pytest.raises(RuntimeError, match="storage unavailable"):
        stage_pdf_upload(
            manifest=_manifest(),
            filename="new-guide.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nnew-content",
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    repository.create_pending_document.assert_not_called()
    storage.remove.assert_not_called()


def test_stage_pdf_upload_removes_object_when_persistence_fails() -> None:
    repository, storage = _dependencies()
    repository.create_pending_document.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        stage_pdf_upload(
            manifest=_manifest(),
            filename="new-guide.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nnew-content",
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    storage.remove.assert_called_once_with("new-guide/new-guide.pdf")


def test_stage_pdf_upload_preserves_persistence_error_if_cleanup_fails() -> None:
    repository, storage = _dependencies()
    repository.create_pending_document.side_effect = RuntimeError("database unavailable")
    storage.remove.side_effect = RuntimeError("cleanup unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        stage_pdf_upload(
            manifest=_manifest(),
            filename="new-guide.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\nnew-content",
            max_bytes=1024,
            repository=repository,
            storage=storage,
        )

    storage.remove.assert_called_once_with("new-guide/new-guide.pdf")
