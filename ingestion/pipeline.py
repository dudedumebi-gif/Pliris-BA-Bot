from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from ingestion.embedding_service import EmbeddingService
from ingestion.manifest_loader import get_manifest_document, resolve_source_path
from ingestion.models import IngestionSummary
from ingestion.page_chunker import chunk_pages
from ingestion.pdf_extractor import extract_pdf
from ingestion.repository import IngestionRepository
from ingestion.storage_service import KnowledgeBaseStorage
from ingestion.text_cleaner import clean_pages
from pliris.config.settings import get_settings


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class IngestionPipeline:
    """End-to-end, idempotent ingestion of one manifest-controlled PDF."""

    def __init__(
        self,
        *,
        manifest_path: Path | None = None,
        private_directory: Path | None = None,
        repository: IngestionRepository | None = None,
        storage: KnowledgeBaseStorage | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.manifest_path = manifest_path
        self.private_directory = private_directory
        self.repository = repository or IngestionRepository()
        self.storage = storage or KnowledgeBaseStorage()
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = get_settings()

    def ingest(
        self,
        document_id: str,
        *,
        dry_run: bool = False,
        max_pages: int | None = None,
        force: bool = False,
        embedding_batch_size: int = 64,
    ) -> IngestionSummary:
        if max_pages is not None and not dry_run:
            raise ValueError(
                "max_pages is allowed only with dry_run to prevent partial production ingestion."
            )

        manifest = get_manifest_document(document_id, self.manifest_path)
        source_path = resolve_source_path(manifest, self.private_directory)
        checksum = sha256_file(source_path)

        extracted = extract_pdf(source_path, max_pages=max_pages)
        cleaned_pages = clean_pages(extracted.pages)
        chunks = chunk_pages(cleaned_pages, document_id=document_id)
        estimated_tokens = sum(chunk.token_count for chunk in chunks)
        warnings = list(extracted.warnings)
        warnings.extend(
            f"Page {page.page_number}: {warning}"
            for page in cleaned_pages
            for warning in page.warnings
        )

        if not chunks:
            raise ValueError("No searchable chunks were produced from the PDF.")

        if dry_run:
            return IngestionSummary(
                document_id=document_id,
                database_document_id=None,
                status="dry_run",
                source_path=str(source_path),
                storage_path=None,
                page_count=len(cleaned_pages),
                chunk_count=len(chunks),
                estimated_embedding_tokens=estimated_tokens,
                warnings=warnings,
            )

        existing = self.repository.get_document(document_id)
        if (
            existing
            and existing["checksum_sha256"] == checksum
            and existing["status"] == "ready"
            and not force
        ):
            return IngestionSummary(
                document_id=document_id,
                database_document_id=str(existing["id"]),
                status="skipped",
                source_path=str(source_path),
                storage_path=existing.get("storage_path"),
                page_count=int(existing.get("page_count") or extracted.page_count),
                chunk_count=0,
                estimated_embedding_tokens=0,
                warnings=[
                    "The same source checksum is already ready. "
                    "Use --force to re-embed and replace its chunks."
                ],
            )

        run_id = self.repository.start_run(
            {
                "manifest_document_id": document_id,
                "source_filename": manifest.source_filename,
                "embedding_model": self.settings.openai_embedding_model,
                "embedding_dimensions": self.settings.openai_embedding_dimensions,
                "chunk_size_tokens": self.settings.chunk_size_tokens,
                "chunk_overlap_tokens": self.settings.chunk_overlap_tokens,
                "force": force,
            }
        )

        database_document_id: UUID | None = None
        storage_path: str | None = None

        try:
            storage_path = self.storage.upload_pdf(
                source_path,
                document_id=document_id,
            )

            database_document_id = self.repository.upsert_processing_document(
                manifest=manifest,
                checksum_sha256=checksum,
                page_count=extracted.page_count,
                storage_bucket=self.settings.supabase_storage_bucket,
                storage_path=storage_path,
                pdf_metadata=extracted.pdf_metadata,
            )

            embedding_result = self.embedding_service.embed_texts(
                [chunk.content for chunk in chunks],
                batch_size=embedding_batch_size,
            )

            self.repository.replace_chunks(
                database_document_id=database_document_id,
                chunks=chunks,
                embeddings=embedding_result.embeddings,
            )
            self.repository.mark_ready(database_document_id)

            self.repository.finish_run(
                run_id,
                status="completed",
                documents_discovered=1,
                documents_processed=1,
                chunks_created=len(chunks),
                chunks_embedded=len(embedding_result.embeddings),
            )

            return IngestionSummary(
                document_id=document_id,
                database_document_id=str(database_document_id),
                status="completed",
                source_path=str(source_path),
                storage_path=storage_path,
                page_count=extracted.page_count,
                chunk_count=len(chunks),
                estimated_embedding_tokens=(embedding_result.input_tokens or estimated_tokens),
                warnings=warnings,
            )

        except Exception as exc:
            if database_document_id is not None:
                self.repository.mark_failed(database_document_id, str(exc))

            self.repository.finish_run(
                run_id,
                status="failed",
                documents_discovered=1,
                documents_processed=0,
                chunks_created=0,
                chunks_embedded=0,
                errors=[
                    {
                        "document_id": document_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                ],
            )
            raise
