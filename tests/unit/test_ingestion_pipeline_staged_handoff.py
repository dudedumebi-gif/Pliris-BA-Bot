from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from ingestion.models import DocumentManifestEntry
from ingestion.pipeline import IngestionPipeline


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        supabase_storage_bucket="knowledge-base",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=1536,
        chunk_size_tokens=800,
        chunk_overlap_tokens=120,
    )


def _services() -> tuple[MagicMock, MagicMock, MagicMock]:
    repository = MagicMock()
    storage = MagicMock()
    embedding_service = MagicMock()
    return repository, storage, embedding_service


@contextmanager
def _pipeline_inputs(
    manifest: DocumentManifestEntry,
) -> Iterator[SimpleNamespace]:
    source_path = Path("data/private/staged-guide.pdf")
    checksum = "e" * 64
    cleaned_page = SimpleNamespace(page_number=1, warnings=[])
    chunk = SimpleNamespace(
        content="Grounded business-analysis content.",
        token_count=17,
    )
    extracted = SimpleNamespace(
        pages=[SimpleNamespace(page_number=1)],
        warnings=[],
        page_count=1,
        pdf_metadata={"producer": "pytest"},
    )

    with (
        patch(
            "ingestion.pipeline.get_settings",
            return_value=_settings(),
        ),
        patch(
            "ingestion.pipeline.get_manifest_document",
            return_value=manifest,
        ),
        patch(
            "ingestion.pipeline.resolve_source_path",
            return_value=source_path,
        ),
        patch(
            "ingestion.pipeline.sha256_file",
            return_value=checksum,
        ),
        patch(
            "ingestion.pipeline.extract_pdf",
            return_value=extracted,
        ),
        patch(
            "ingestion.pipeline.clean_pages",
            return_value=[cleaned_page],
        ),
        patch(
            "ingestion.pipeline.chunk_pages",
            return_value=[chunk],
        ),
    ):
        yield SimpleNamespace(
            source_path=source_path,
            checksum=checksum,
            extracted=extracted,
            chunks=[chunk],
        )


def test_staged_ingestion_claims_exact_row_without_uploading() -> None:
    manifest = DocumentManifestEntry(
        document_id="staged-guide",
        title="Staged Guide",
        source_filename="staged-guide.pdf",
        author="Example Author",
        publication_year=2026,
    )
    staged_document_id = uuid4()
    run_id = uuid4()
    expected_storage_path = "staged-guide/staged-guide.pdf"

    repository, storage, embedding_service = _services()
    repository.get_document.return_value = {
        "id": staged_document_id,
        "checksum_sha256": "e" * 64,
        "status": "pending",
        "storage_path": expected_storage_path,
        "page_count": None,
    }
    repository.start_run.return_value = run_id
    repository.claim_pending_document.return_value = staged_document_id
    storage.build_storage_path.return_value = expected_storage_path
    embedding_service.embed_texts.return_value = SimpleNamespace(
        embeddings=[[0.1, 0.2]],
        input_tokens=17,
    )

    with _pipeline_inputs(manifest) as inputs:
        summary = IngestionPipeline(
            repository=repository,
            storage=storage,
            embedding_service=embedding_service,
        ).ingest(
            "staged-guide",
            staged_document_id=staged_document_id,
        )

    assert summary.status == "completed"
    assert summary.database_document_id == str(staged_document_id)
    assert summary.storage_path == expected_storage_path

    storage.upload_pdf.assert_not_called()
    repository.upsert_processing_document.assert_not_called()

    storage.build_storage_path.assert_called_once_with(
        "staged-guide",
        "staged-guide.pdf",
    )
    repository.claim_pending_document.assert_called_once_with(
        database_document_id=staged_document_id,
        manifest=manifest,
        checksum_sha256=inputs.checksum,
        page_count=inputs.extracted.page_count,
        storage_bucket="knowledge-base",
        storage_path=expected_storage_path,
        pdf_metadata=inputs.extracted.pdf_metadata,
    )

    embedding_service.embed_texts.assert_called_once_with(
        ["Grounded business-analysis content."],
        batch_size=64,
    )
    repository.replace_chunks.assert_called_once_with(
        database_document_id=staged_document_id,
        chunks=inputs.chunks,
        embeddings=[[0.1, 0.2]],
    )
    repository.mark_ready.assert_called_once_with(staged_document_id)
    repository.mark_failed.assert_not_called()


def test_failed_staged_claim_prevents_embedding_and_failure_transition() -> None:
    manifest = DocumentManifestEntry(
        document_id="staged-guide",
        title="Staged Guide",
        source_filename="staged-guide.pdf",
    )
    staged_document_id = uuid4()
    run_id = uuid4()

    repository, storage, embedding_service = _services()
    repository.get_document.return_value = {
        "id": staged_document_id,
        "checksum_sha256": "e" * 64,
        "status": "ready",
        "storage_path": "staged-guide/staged-guide.pdf",
        "page_count": 1,
    }
    repository.start_run.return_value = run_id
    repository.claim_pending_document.side_effect = ValueError(
        "The staged document could not be claimed."
    )
    storage.build_storage_path.return_value = "staged-guide/staged-guide.pdf"

    with (
        _pipeline_inputs(manifest),
        pytest.raises(
            ValueError,
            match="staged document could not be claimed",
        ),
    ):
        IngestionPipeline(
            repository=repository,
            storage=storage,
            embedding_service=embedding_service,
        ).ingest(
            "staged-guide",
            staged_document_id=staged_document_id,
        )

    storage.upload_pdf.assert_not_called()
    repository.upsert_processing_document.assert_not_called()
    embedding_service.embed_texts.assert_not_called()
    repository.replace_chunks.assert_not_called()
    repository.mark_ready.assert_not_called()
    repository.mark_failed.assert_not_called()

    repository.finish_run.assert_called_once()
    assert repository.finish_run.call_args.args == (run_id,)
    assert repository.finish_run.call_args.kwargs["status"] == "failed"
    assert repository.finish_run.call_args.kwargs["documents_processed"] == 0


def test_staged_ingestion_rejects_force_before_repository_access() -> None:
    repository, storage, embedding_service = _services()

    with (
        patch(
            "ingestion.pipeline.get_settings",
            return_value=_settings(),
        ),
        pytest.raises(
            ValueError,
            match="--force may not be used with a staged document",
        ),
    ):
        IngestionPipeline(
            repository=repository,
            storage=storage,
            embedding_service=embedding_service,
        ).ingest(
            "staged-guide",
            force=True,
            staged_document_id=uuid4(),
        )

    repository.get_document.assert_not_called()
    repository.start_run.assert_not_called()
    repository.claim_pending_document.assert_not_called()
    storage.upload_pdf.assert_not_called()
    embedding_service.embed_texts.assert_not_called()


def test_legacy_unstaged_ingestion_still_uploads_and_upserts() -> None:
    manifest = DocumentManifestEntry(
        document_id="legacy-guide",
        title="Legacy Guide",
        source_filename="legacy-guide.pdf",
    )
    database_document_id = uuid4()
    run_id = uuid4()
    uploaded_storage_path = "legacy-guide/legacy-guide.pdf"

    repository, storage, embedding_service = _services()
    repository.get_document.return_value = None
    repository.start_run.return_value = run_id
    repository.upsert_processing_document.return_value = database_document_id
    storage.upload_pdf.return_value = uploaded_storage_path
    embedding_service.embed_texts.return_value = SimpleNamespace(
        embeddings=[[0.3, 0.4]],
        input_tokens=17,
    )

    with _pipeline_inputs(manifest):
        summary = IngestionPipeline(
            repository=repository,
            storage=storage,
            embedding_service=embedding_service,
        ).ingest("legacy-guide")

    assert summary.status == "completed"
    storage.upload_pdf.assert_called_once()
    repository.upsert_processing_document.assert_called_once()
    repository.claim_pending_document.assert_not_called()
    storage.build_storage_path.assert_not_called()
    repository.mark_ready.assert_called_once_with(database_document_id)
