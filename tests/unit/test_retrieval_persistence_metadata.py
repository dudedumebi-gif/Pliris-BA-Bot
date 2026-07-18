from __future__ import annotations

from pliris.retrieval.hosted_hybrid import (
    HostedHybridRetriever,
    manifest_ids_from_chunks,
)


def test_normalized_result_preserves_rpc_component_ranks() -> None:
    result = HostedHybridRetriever._normalize_row(
        {
            "chunk_id": "chunk-1",
            "document_id": "document-1",
            "document_title": "BABOK Guide",
            "content": "Requirements traceability records lineage.",
            "page_start": 87,
            "page_end": 91,
            "score": 0.038,
            "semantic_rank": 2,
            "keyword_rank": 1,
            "metadata": {"manifest_document_id": "babok-v3"},
        },
        rank=1,
    )

    assert result.source == "babok-v3"
    assert result.metadata["semantic_rank"] == 2
    assert result.metadata["keyword_rank"] == 1
    assert manifest_ids_from_chunks([result]) == {"babok-v3"}


def test_normalized_result_omits_missing_component_rank() -> None:
    result = HostedHybridRetriever._normalize_row(
        {
            "chunk_id": "chunk-2",
            "content": "Semantic-only evidence.",
            "document_title": "Source",
            "semantic_rank": "3",
            "keyword_rank": None,
        },
        rank=2,
    )

    assert result.metadata["semantic_rank"] == 3
    assert "keyword_rank" not in result.metadata
