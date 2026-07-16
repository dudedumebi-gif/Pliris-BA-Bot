from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from ingestion.models import DocumentChunk, DocumentManifestEntry
from pliris.config.settings import get_settings
from pliris.database.postgres import postgres_connection


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(value, ".10g") for value in values) + "]"


class IngestionRepository:
    """Transactional persistence for documents, chunks, and ingestion audits."""

    def get_document(self, manifest_id: str) -> dict[str, Any] | None:
        with postgres_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    select id, manifest_id, checksum_sha256, status, storage_path,
                           page_count, metadata
                    from public.documents
                    where manifest_id = %s
                    """,
                (manifest_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def start_run(self, configuration: dict[str, Any]) -> UUID:
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.ingestion_runs (status, configuration)
                    values ('running', %s)
                    returning id
                    """,
                    (Jsonb(configuration),),
                )
                run_id = cursor.fetchone()["id"]
            connection.commit()
        return run_id

    def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        documents_discovered: int,
        documents_processed: int,
        chunks_created: int,
        chunks_embedded: int,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        error_list = errors or []
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.ingestion_runs
                    set status = %s,
                        completed_at = now(),
                        documents_discovered = %s,
                        documents_processed = %s,
                        chunks_created = %s,
                        chunks_embedded = %s,
                        error_count = %s,
                        errors = %s
                    where id = %s
                    """,
                    (
                        status,
                        documents_discovered,
                        documents_processed,
                        chunks_created,
                        chunks_embedded,
                        len(error_list),
                        Jsonb(error_list),
                        run_id,
                    ),
                )
            connection.commit()

    def upsert_processing_document(
        self,
        *,
        manifest: DocumentManifestEntry,
        checksum_sha256: str,
        page_count: int,
        storage_bucket: str,
        storage_path: str,
        pdf_metadata: dict[str, Any],
    ) -> UUID:
        metadata = {
            **manifest.metadata,
            "manifest_document_id": manifest.document_id,
            "source_type": manifest.source_type,
            "access": manifest.access,
            "include_in_public_repository": manifest.include_in_public_repository,
            "pdf_metadata": pdf_metadata,
        }

        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.documents (
                        manifest_id, title, source_filename, storage_bucket,
                        storage_path, author, edition, publication_year,
                        mime_type, checksum_sha256, page_count, status,
                        ingestion_error, metadata
                    )
                    values (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        'application/pdf', %s, %s, 'processing', null, %s
                    )
                    on conflict (manifest_id) where manifest_id is not null
                    do update set
                        title = excluded.title,
                        source_filename = excluded.source_filename,
                        storage_bucket = excluded.storage_bucket,
                        storage_path = excluded.storage_path,
                        author = excluded.author,
                        edition = excluded.edition,
                        publication_year = excluded.publication_year,
                        checksum_sha256 = excluded.checksum_sha256,
                        page_count = excluded.page_count,
                        status = 'processing',
                        ingestion_error = null,
                        metadata = excluded.metadata,
                        updated_at = now()
                    returning id
                    """,
                    (
                        manifest.document_id,
                        manifest.title,
                        manifest.source_filename,
                        storage_bucket,
                        storage_path,
                        manifest.author,
                        manifest.edition,
                        manifest.publication_year,
                        checksum_sha256,
                        page_count,
                        Jsonb(metadata),
                    ),
                )
                document_id = cursor.fetchone()["id"]
            connection.commit()
        return document_id

    def replace_chunks(
        self,
        *,
        database_document_id: UUID,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts do not match.")

        settings = get_settings()

        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.document_chunks where document_id = %s",
                    (database_document_id,),
                )

                rows = []
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    rows.append(
                        (
                            database_document_id,
                            chunk.chunk_index,
                            chunk.content,
                            chunk.page_start,
                            chunk.page_end,
                            chunk.chapter,
                            chunk.section,
                            chunk.heading_path,
                            chunk.token_count,
                            chunk.content_hash,
                            _vector_literal(embedding),
                            settings.openai_embedding_model,
                            settings.openai_embedding_dimensions,
                            Jsonb(chunk.metadata),
                        )
                    )

                cursor.executemany(
                    """
                    insert into public.document_chunks (
                        document_id, chunk_index, content, page_start, page_end,
                        chapter, section, heading_path, token_count, content_hash,
                        embedding, embedding_model, embedding_dimensions, metadata
                    )
                    values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::extensions.vector, %s, %s, %s
                    )
                    """,
                    rows,
                )
            connection.commit()

    def mark_ready(self, database_document_id: UUID) -> None:
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.documents
                    set status = 'ready',
                        ingestion_error = null,
                        last_ingested_at = now(),
                        updated_at = now()
                    where id = %s
                    """,
                    (database_document_id,),
                )
            connection.commit()

    def mark_failed(self, database_document_id: UUID, error: str) -> None:
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update public.documents
                    set status = 'failed',
                        ingestion_error = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (error[:4000], database_document_id),
                )
            connection.commit()

    def delete_document(self, manifest_id: str) -> None:
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from public.documents where manifest_id = %s",
                    (manifest_id,),
                )
            connection.commit()
