from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ingestion.embedding_service import EmbeddingService
from pliris.config.settings import get_settings
from pliris.database.supabase_client import get_supabase_admin_client


@dataclass(frozen=True, slots=True)
class RetrievalWeights:
    full_text_weight: float
    semantic_weight: float


class HostedRetrievalAdapter:
    """
    Evaluate lexical, semantic, and hybrid ranking through the hosted RPC.

    The production `hybrid_search` function remains the single source of truth.
    Lexical and semantic baselines disable the opposite ranking arm by assigning
    it a zero weight.
    """

    VALID_METHODS = frozenset({"lexical", "semantic", "hybrid"})

    def __init__(
        self,
        method: str,
        *,
        client: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        settings: Any | None = None,
    ) -> None:
        normalized_method = method.strip().lower()
        if normalized_method not in self.VALID_METHODS:
            raise ValueError(f"Unsupported hosted retrieval method: {method!r}.")

        self.method = normalized_method
        self.client = client or get_supabase_admin_client()
        self.embedding_service = embedding_service or EmbeddingService()
        self.settings = settings or get_settings()
        self._document_id_cache: dict[str, list[str]] = {}

    def _weights(self) -> RetrievalWeights:
        if self.method == "lexical":
            return RetrievalWeights(
                full_text_weight=1.0,
                semantic_weight=0.0,
            )

        if self.method == "semantic":
            return RetrievalWeights(
                full_text_weight=0.0,
                semantic_weight=1.0,
            )

        return RetrievalWeights(
            full_text_weight=float(self.settings.full_text_weight),
            semantic_weight=float(self.settings.semantic_weight),
        )

    def _resolve_document_ids(
        self,
        manifest_id: str | None,
    ) -> list[str] | None:
        if not manifest_id:
            return None

        cached = self._document_id_cache.get(manifest_id)
        if cached is not None:
            return cached

        response = (
            self.client.table("documents").select("id").eq("manifest_id", manifest_id).execute()
        )
        rows = response.data or []
        document_ids = [str(row["id"]) for row in rows if row.get("id")]

        if not document_ids:
            raise ValueError(f"Document not found for manifest id {manifest_id!r}.")

        self._document_id_cache[manifest_id] = document_ids
        return document_ids

    @staticmethod
    def _manifest_id_from_filters(
        filters: dict[str, Any] | None,
    ) -> str | None:
        if not filters:
            return None

        value = filters.get("document_id")
        if value in (None, ""):
            value = filters.get("manifest_id")

        return str(value) if value not in (None, "") else None

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if top_k < 1:
            raise ValueError("top_k must be positive.")

        manifest_id = document_id or self._manifest_id_from_filters(filters)
        filter_document_ids = self._resolve_document_ids(manifest_id)

        embedding_result = self.embedding_service.embed_texts([query])
        query_embedding = embedding_result.embeddings[0]
        weights = self._weights()

        response = self.client.rpc(
            "hybrid_search",
            {
                "query_text": query,
                "query_embedding": query_embedding,
                "match_count": top_k,
                "full_text_weight": (weights.full_text_weight),
                "semantic_weight": weights.semantic_weight,
                "rrf_k": int(self.settings.rrf_k),
                "filter_document_ids": filter_document_ids,
            },
        ).execute()

        rows = response.data or []
        results: list[dict[str, Any]] = []

        for rank, row in enumerate(rows, start=1):
            page_start = row.get("page_start")
            page_end = row.get("page_end")
            result_id = (
                row.get("chunk_id")
                or row.get("id")
                or (f"{manifest_id or 'all'}:{page_start}:{page_end}:{rank}")
            )

            metadata = dict(row.get("metadata") or {})
            metadata.update(
                {
                    "page_start": page_start,
                    "page_end": page_end,
                    "document_title": row.get("document_title"),
                    "retrieval_method": self.method,
                }
            )

            results.append(
                {
                    "id": str(result_id),
                    "text": str(row.get("content") or ""),
                    "title": row.get("document_title"),
                    "page_start": page_start,
                    "page_end": page_end,
                    "score": float(row.get("score") or 0.0),
                    "metadata": metadata,
                }
            )

        return results
