from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID


class DocumentRepository:
    """Read-only source inspection against the authoritative knowledge base."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], AbstractContextManager[Any]] | None = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection
        self.connection_factory = connection_factory

    async def list_documents(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        normalized_query = query.strip()[:200] if query else None
        return await asyncio.to_thread(
            self._list_documents_sync,
            limit,
            offset,
            status,
            normalized_query,
        )

    def _list_documents_sync(
        self,
        limit: int,
        offset: int,
        status: str | None,
        query: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        where_sql, parameters = self._document_filters(status=status, query=query)
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                f"select count(*)::int as total from public.documents as d {where_sql}",
                parameters,
            )
            total_row = cursor.fetchone()
            total = int(total_row["total"]) if total_row else 0
            cursor.execute(
                f"""
                select
                  d.id, d.manifest_id, d.title, d.source_filename, d.author,
                  coalesce(d.metadata ->> 'source_type', 'unknown') as source_type,
                  coalesce(d.metadata ->> 'access', 'private') as access,
                  d.status, d.page_count,
                  coalesce(chunks.chunk_count, 0)::int as chunk_count,
                  coalesce(chunks.total_tokens, 0)::int as total_tokens,
                  d.last_ingested_at, d.created_at, d.updated_at
                from public.documents as d
                left join (
                  select document_id, count(*)::int as chunk_count,
                         coalesce(sum(token_count), 0)::int as total_tokens
                  from public.document_chunks
                  group by document_id
                ) as chunks on chunks.document_id = d.id
                {where_sql}
                order by lower(d.title), d.created_at, d.id
                limit %s offset %s
                """,
                (*parameters, limit, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        return rows, total

    async def get_by_id(self, document_id: UUID) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._get_by_id_sync, document_id)

    def _get_by_id_sync(self, document_id: UUID) -> dict[str, Any] | None:
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                select
                  d.id, d.manifest_id, d.title, d.source_filename, d.author,
                  d.edition, d.publication_year, d.mime_type, d.checksum_sha256,
                  d.metadata,
                  coalesce(d.metadata ->> 'source_type', 'unknown') as source_type,
                  coalesce(d.metadata ->> 'access', 'private') as access,
                  d.status, d.page_count,
                  coalesce(chunks.chunk_count, 0)::int as chunk_count,
                  coalesce(chunks.total_tokens, 0)::int as total_tokens,
                  d.last_ingested_at, d.created_at, d.updated_at,
                  (d.ingestion_error is not null and length(btrim(d.ingestion_error)) > 0)
                    as has_ingestion_error
                from public.documents as d
                left join (
                  select document_id, count(*)::int as chunk_count,
                         coalesce(sum(token_count), 0)::int as total_tokens
                  from public.document_chunks
                  group by document_id
                ) as chunks on chunks.document_id = d.id
                where d.id = %s
                """,
                (document_id,),
            )
            row = cursor.fetchone()
        return dict(row) if row else None

    async def get_stats(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._get_stats_sync)

    def _get_stats_sync(self) -> dict[str, Any]:
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                select
                  count(*)::int as total_documents,
                  coalesce(sum(d.page_count), 0)::int as total_pages,
                  coalesce(sum(chunks.chunk_count), 0)::int as total_chunks,
                  coalesce(sum(chunks.total_tokens), 0)::int as total_tokens,
                  count(*) filter (where d.status = 'ready')::int as ready_documents,
                  count(*) filter (where d.status = 'pending')::int as pending_documents,
                  count(*) filter (where d.status = 'processing')::int as processing_documents,
                  count(*) filter (where d.status = 'failed')::int as failed_documents,
                  count(*) filter (where d.status = 'archived')::int as archived_documents,
                  max(d.last_ingested_at) as last_ingested_at
                from public.documents as d
                left join (
                  select document_id, count(*)::int as chunk_count,
                         coalesce(sum(token_count), 0)::int as total_tokens
                  from public.document_chunks
                  group by document_id
                ) as chunks on chunks.document_id = d.id
                """
            )
            row = cursor.fetchone()
        return dict(row)

    async def list_chunks(
        self,
        document_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        return await asyncio.to_thread(
            self._list_chunks_sync,
            document_id,
            limit,
            offset,
        )

    def _list_chunks_sync(
        self,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                "select count(*)::int as total from public.document_chunks where document_id = %s",
                (document_id,),
            )
            total_row = cursor.fetchone()
            total = int(total_row["total"]) if total_row else 0
            cursor.execute(
                """
                select id, chunk_index, content, page_start, page_end,
                       chapter, section, heading_path, token_count, content_hash,
                       embedding_model, created_at, updated_at
                from public.document_chunks
                where document_id = %s
                order by chunk_index, id
                limit %s offset %s
                """,
                (document_id, limit, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        return rows, total

    @staticmethod
    def _document_filters(
        *,
        status: str | None,
        query: str | None,
    ) -> tuple[str, tuple[Any, ...]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if status is not None:
            clauses.append("d.status = %s")
            parameters.append(status)
        if query:
            clauses.append(
                "(d.title ilike %s or d.source_filename ilike %s or "
                "coalesce(d.author, '') ilike %s or coalesce(d.manifest_id, '') ilike %s)"
            )
            pattern = f"%{query}%"
            parameters.extend([pattern, pattern, pattern, pattern])
        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        return where_sql, tuple(parameters)
