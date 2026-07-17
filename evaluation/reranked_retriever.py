from __future__ import annotations

from typing import Any

from evaluation.local_reranker import LocalCrossEncoderReranker


class RerankedHostedRetriever:
    """Retrieve a wider hosted hybrid candidate set, then rerank locally."""

    def __init__(
        self,
        *,
        base_retriever: Any | None = None,
        reranker: LocalCrossEncoderReranker | None = None,
        candidate_multiplier: int = 4,
        minimum_candidates: int = 20,
    ) -> None:
        if candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be positive.")
        if minimum_candidates < 1:
            raise ValueError("minimum_candidates must be positive.")

        if base_retriever is None:
            from evaluation.hosted_retriever import (
                HostedRetrievalAdapter,
            )

            self.base_retriever = HostedRetrievalAdapter(method="hybrid")
        else:
            self.base_retriever = base_retriever
        self.reranker = reranker if reranker is not None else LocalCrossEncoderReranker()
        self.candidate_multiplier = candidate_multiplier
        self.minimum_candidates = minimum_candidates

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if top_k < 1:
            raise ValueError("top_k must be positive.")

        candidate_count = max(
            self.minimum_candidates,
            top_k * self.candidate_multiplier,
        )
        candidates = await self.base_retriever.search(
            query=query,
            top_k=candidate_count,
            filters=filters,
            document_id=document_id,
        )
        if not candidates:
            return []

        return self.reranker.rerank(
            query,
            candidates,
            top_k=top_k,
        )
