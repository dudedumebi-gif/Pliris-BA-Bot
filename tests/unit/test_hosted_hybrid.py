from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pliris.retrieval.hosted_hybrid import (
    HostedHybridRetriever,
    manifest_ids_from_chunks,
)


class FakeTableRequest:
    def __init__(
        self,
        client: FakeClient,
        rows: list[dict[str, Any]],
    ) -> None:
        self.client = client
        self.rows = rows

    def select(self, columns: str) -> FakeTableRequest:
        self.client.selected_columns.append(columns)
        return self

    def eq(
        self,
        column: str,
        value: Any,
    ) -> FakeTableRequest:
        self.client.table_filters.append((column, value))
        return self

    def execute(self) -> SimpleNamespace:
        self.client.table_execute_count += 1
        return SimpleNamespace(data=self.rows)


class FakeRPCRequest:
    def __init__(
        self,
        client: FakeClient,
        rows: list[dict[str, Any]],
    ) -> None:
        self.client = client
        self.rows = rows

    def execute(self) -> SimpleNamespace:
        self.client.rpc_execute_count += 1
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(
        self,
        *,
        document_rows: list[dict[str, Any]] | None = None,
        search_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.document_rows = (
            document_rows if document_rows is not None else [{"id": "database-document-id"}]
        )
        self.search_rows = (
            search_rows
            if search_rows is not None
            else [
                {
                    "chunk_id": "chunk-1",
                    "document_id": "database-document-id",
                    "content": ("Business analysis is the practice of enabling change."),
                    "document_title": "BABOK Guide",
                    "page_start": 12,
                    "page_end": 14,
                    "score": 0.038,
                    "metadata": {
                        "manifest_id": "babok-v3",
                        "storage_path": "babok-v3/guide.pdf",
                    },
                }
            ]
        )
        self.selected_columns: list[str] = []
        self.table_filters: list[tuple[str, Any]] = []
        self.table_execute_count = 0
        self.rpc_execute_count = 0
        self.rpc_calls: list[tuple[str, dict[str, Any]]] = []

    def table(self, name: str) -> FakeTableRequest:
        assert name == "documents"
        return FakeTableRequest(self, self.document_rows)

    def rpc(
        self,
        name: str,
        parameters: dict[str, Any],
    ) -> FakeRPCRequest:
        self.rpc_calls.append((name, parameters))
        return FakeRPCRequest(self, self.search_rows)


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(
        self,
        texts: list[str],
    ) -> SimpleNamespace:
        self.calls.append(texts)
        return SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]])


@pytest.fixture
def settings() -> SimpleNamespace:
    return SimpleNamespace(
        full_text_weight=0.4,
        semantic_weight=0.6,
        rrf_k=60,
    )


@pytest.mark.asyncio
async def test_search_calls_hosted_rpc_and_normalizes_results(
    settings: SimpleNamespace,
) -> None:
    client = FakeClient()
    embeddings = FakeEmbeddingService()
    retriever = HostedHybridRetriever(
        client=client,
        embedding_service=embeddings,
        settings=settings,
    )

    results = await retriever.search(
        "  What is business analysis?  ",
        top_k=5,
        document_id="babok-v3",
    )

    assert len(results) == 1
    assert results[0].rank == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].title == "BABOK Guide"
    assert results[0].source == "babok-v3/guide.pdf"
    assert results[0].page_label == "12-14"
    assert results[0].score == pytest.approx(0.038)
    assert embeddings.calls == [["What is business analysis?"]]

    rpc_name, parameters = client.rpc_calls[0]
    assert rpc_name == "hybrid_search"
    assert parameters == {
        "query_text": "What is business analysis?",
        "query_embedding": [0.1, 0.2, 0.3],
        "match_count": 5,
        "full_text_weight": 0.4,
        "semantic_weight": 0.6,
        "rrf_k": 60,
        "filter_document_ids": ["database-document-id"],
    }
    assert client.rpc_execute_count == 1


@pytest.mark.asyncio
async def test_search_caches_manifest_lookup(
    settings: SimpleNamespace,
) -> None:
    client = FakeClient()
    retriever = HostedHybridRetriever(
        client=client,
        embedding_service=FakeEmbeddingService(),
        settings=settings,
    )

    await retriever.search(
        "Question one",
        document_id="babok-v3",
    )
    await retriever.search(
        "Question two",
        document_id="babok-v3",
    )

    assert client.table_execute_count == 1
    assert client.table_filters == [("manifest_id", "babok-v3")]
    assert client.rpc_execute_count == 2


@pytest.mark.asyncio
async def test_search_without_document_filter_passes_none(
    settings: SimpleNamespace,
) -> None:
    client = FakeClient()
    retriever = HostedHybridRetriever(
        client=client,
        embedding_service=FakeEmbeddingService(),
        settings=settings,
    )

    await retriever.search("What is stakeholder analysis?")

    _, parameters = client.rpc_calls[0]
    assert parameters["filter_document_ids"] is None
    assert client.table_execute_count == 0


@pytest.mark.asyncio
async def test_search_rejects_unknown_manifest(
    settings: SimpleNamespace,
) -> None:
    retriever = HostedHybridRetriever(
        client=FakeClient(document_rows=[]),
        embedding_service=FakeEmbeddingService(),
        settings=settings,
    )

    with pytest.raises(
        ValueError,
        match="Document not found",
    ):
        await retriever.search(
            "What is traceability?",
            document_id="missing",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "top_k", "message"),
    [
        ("   ", 5, "query must not be blank"),
        ("Question", 0, "top_k must be positive"),
        ("Question", 51, "top_k cannot exceed 50"),
    ],
)
async def test_search_validates_inputs(
    settings: SimpleNamespace,
    query: str,
    top_k: int,
    message: str,
) -> None:
    retriever = HostedHybridRetriever(
        client=FakeClient(),
        embedding_service=FakeEmbeddingService(),
        settings=settings,
    )

    with pytest.raises(ValueError, match=message):
        await retriever.search(query, top_k=top_k)


def test_normalize_row_handles_sparse_metadata() -> None:
    result = HostedHybridRetriever._normalize_row(
        {
            "id": "chunk-2",
            "text": "Sparse result text.",
            "title": "Source Document",
            "page_start": "22",
            "combined_score": "0.25",
        },
        rank=2,
    )

    assert result.chunk_id == "chunk-2"
    assert result.document_id is None
    assert result.page_start == 22
    assert result.page_end == 22
    assert result.page_label == "22"
    assert result.score == pytest.approx(0.25)


def test_live_manifest_metadata_is_normalized() -> None:
    result = HostedHybridRetriever._normalize_row(
        {
            "chunk_id": "chunk-live",
            "content": "Requirements traceability identifies lineage.",
            "document_title": "BABOK Guide",
            "page_start": 87,
            "page_end": 91,
            "score": 0.038,
            "metadata": {
                "manifest_document_id": "babok-v3",
            },
        },
        rank=1,
    )

    assert result.source == "babok-v3"
    assert manifest_ids_from_chunks([result]) == {"babok-v3"}
