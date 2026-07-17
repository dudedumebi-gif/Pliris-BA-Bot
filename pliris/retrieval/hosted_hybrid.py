from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from pliris.retrieval.models import RetrievedChunk


class HostedHybridRetriever:
    """
    Production retrieval through the hosted Supabase `hybrid_search` RPC.

    Supabase and embedding calls are synchronous in the current project, so the
    public async method moves the blocking work to a worker thread.
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        embedding_service: Any | None = None,
        settings: Any | None = None,
    ) -> None:
        if client is None:
            from pliris.database.supabase_client import (
                get_supabase_admin_client,
            )

            client = get_supabase_admin_client()

        if embedding_service is None:
            from ingestion.embedding_service import EmbeddingService

            embedding_service = EmbeddingService()

        if settings is None:
            from pliris.config.settings import get_settings

            settings = get_settings()

        self.client = client
        self.embedding_service = embedding_service
        self.settings = settings
        self._document_id_cache: dict[str, tuple[str, ...]] = {}

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        document_id: str | None = None,
    ) -> list[RetrievedChunk]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be blank.")
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        if top_k > 50:
            raise ValueError("top_k cannot exceed 50.")

        return await asyncio.to_thread(
            self._search_sync,
            normalized_query,
            top_k,
            document_id,
        )

    def _search_sync(
        self,
        query: str,
        top_k: int,
        document_id: str | None,
    ) -> list[RetrievedChunk]:
        filter_document_ids = self._resolve_document_ids(document_id)
        embedding_result = self.embedding_service.embed_texts([query])
        query_embedding = embedding_result.embeddings[0]

        response = self.client.rpc(
            "hybrid_search",
            {
                "query_text": query,
                "query_embedding": query_embedding,
                "match_count": top_k,
                "full_text_weight": float(self.settings.full_text_weight),
                "semantic_weight": float(self.settings.semantic_weight),
                "rrf_k": int(self.settings.rrf_k),
                "filter_document_ids": filter_document_ids,
            },
        ).execute()

        rows = response.data or []
        return [self._normalize_row(row, rank=index) for index, row in enumerate(rows, start=1)]

    def _resolve_document_ids(
        self,
        manifest_id: str | None,
    ) -> list[str] | None:
        if not manifest_id:
            return None

        cached = self._document_id_cache.get(manifest_id)
        if cached is not None:
            return list(cached)

        response = (
            self.client.table("documents").select("id").eq("manifest_id", manifest_id).execute()
        )
        rows = response.data or []
        ids = tuple(str(row["id"]) for row in rows if row.get("id") not in (None, ""))

        if not ids:
            raise ValueError(f"Document not found for manifest id {manifest_id!r}.")

        self._document_id_cache[manifest_id] = ids
        return list(ids)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _metadata(row: dict[str, Any]) -> dict[str, Any]:
        metadata = row.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}

    @classmethod
    def _normalize_row(
        cls,
        row: dict[str, Any],
        *,
        rank: int,
    ) -> RetrievedChunk:
        metadata = cls._metadata(row)
        page_start = cls._optional_int(row.get("page_start", metadata.get("page_start")))
        page_end = cls._optional_int(row.get("page_end", metadata.get("page_end")))

        if page_start is not None and page_end is None:
            page_end = page_start
        if page_end is not None and page_start is None:
            page_start = page_end

        title = str(
            row.get("document_title")
            or row.get("title")
            or metadata.get("document_title")
            or metadata.get("title")
            or "Knowledge Base Document"
        )
        manifest_id = metadata.get("manifest_document_id") or metadata.get("manifest_id")

        source = str(
            row.get("source")
            or metadata.get("source")
            or metadata.get("storage_path")
            or manifest_id
            or title
        )

        document_id = row.get("document_id") or metadata.get("document_id")
        chunk_id = (
            row.get("chunk_id")
            or row.get("id")
            or metadata.get("chunk_id")
            or f"{document_id or title}:{page_start}:{page_end}:{rank}"
        )

        score_value = row.get(
            "score",
            row.get("combined_score", 0.0),
        )
        try:
            score = float(score_value or 0.0)
        except (TypeError, ValueError):
            score = 0.0

        return RetrievedChunk(
            rank=rank,
            chunk_id=str(chunk_id),
            text=str(
                row.get("content")
                or row.get("text")
                or metadata.get("content")
                or metadata.get("text")
                or ""
            ),
            title=title,
            source=source,
            page_start=page_start,
            page_end=page_end,
            score=score,
            document_id=(str(document_id) if document_id not in (None, "") else None),
            metadata=metadata,
        )


def manifest_ids_from_chunks(
    chunks: Sequence[RetrievedChunk],
) -> set[str]:
    """Return manifest identifiers carried in result metadata."""

    identifiers: set[str] = set()

    for chunk in chunks:
        manifest_id = chunk.metadata.get("manifest_document_id") or chunk.metadata.get(
            "manifest_id"
        )
        if manifest_id not in (None, ""):
            identifiers.add(str(manifest_id))

    return identifiers
