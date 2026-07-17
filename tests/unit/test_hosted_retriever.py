from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from evaluation.hosted_retriever import HostedRetrievalAdapter


class FakeTableRequest:
    def __init__(
        self,
        client: FakeClient,
        rows: list[dict[str, Any]],
    ) -> None:
        self.client = client
        self.rows = rows

    def select(self, _columns: str) -> FakeTableRequest:
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
                    "content": "Business analysis enables change.",
                    "document_title": "BABOK",
                    "page_start": 12,
                    "page_end": 14,
                    "score": 0.5,
                }
            ]
        )

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
        self.queries: list[list[str]] = []

    def embed_texts(
        self,
        texts: list[str],
    ) -> SimpleNamespace:
        self.queries.append(texts)
        return SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]])


@pytest.fixture
def settings() -> SimpleNamespace:
    return SimpleNamespace(
        full_text_weight=0.4,
        semantic_weight=0.6,
        rrf_k=60,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "full_text_weight", "semantic_weight"),
    [
        ("lexical", 1.0, 0.0),
        ("semantic", 0.0, 1.0),
        ("hybrid", 0.4, 0.6),
    ],
)
async def test_hosted_adapter_uses_expected_weights(
    settings: SimpleNamespace,
    method: str,
    full_text_weight: float,
    semantic_weight: float,
) -> None:
    client = FakeClient()
    embedding_service = FakeEmbeddingService()
    adapter = HostedRetrievalAdapter(
        method,
        client=client,
        embedding_service=embedding_service,
        settings=settings,
    )

    results = await adapter.search(
        "What is business analysis?",
        top_k=5,
        document_id="babok-v3",
    )

    assert len(results) == 1
    assert results[0]["id"] == "chunk-1"
    assert results[0]["page_start"] == 12
    assert results[0]["page_end"] == 14

    rpc_name, parameters = client.rpc_calls[0]
    assert rpc_name == "hybrid_search"
    assert parameters["full_text_weight"] == pytest.approx(full_text_weight)
    assert parameters["semantic_weight"] == pytest.approx(semantic_weight)
    assert parameters["filter_document_ids"] == ["database-document-id"]
    assert parameters["match_count"] == 5
    assert embedding_service.queries == [["What is business analysis?"]]
    assert client.rpc_execute_count == 1


@pytest.mark.asyncio
async def test_hosted_adapter_caches_document_lookup(
    settings: SimpleNamespace,
) -> None:
    client = FakeClient()
    adapter = HostedRetrievalAdapter(
        "hybrid",
        client=client,
        embedding_service=FakeEmbeddingService(),
        settings=settings,
    )

    await adapter.search(
        "Question one",
        document_id="babok-v3",
    )
    await adapter.search(
        "Question two",
        document_id="babok-v3",
    )

    assert client.table_execute_count == 1
    assert client.table_filters == [("manifest_id", "babok-v3")]
    assert client.rpc_execute_count == 2


@pytest.mark.asyncio
async def test_hosted_adapter_rejects_missing_document(
    settings: SimpleNamespace,
) -> None:
    client = FakeClient(document_rows=[])
    adapter = HostedRetrievalAdapter(
        "semantic",
        client=client,
        embedding_service=FakeEmbeddingService(),
        settings=settings,
    )

    with pytest.raises(
        ValueError,
        match="Document not found",
    ):
        await adapter.search(
            "What is requirements traceability?",
            document_id="missing",
        )


def test_hosted_adapter_rejects_unknown_method(
    settings: SimpleNamespace,
) -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported hosted retrieval method",
    ):
        HostedRetrievalAdapter(
            "unknown",
            client=FakeClient(),
            embedding_service=FakeEmbeddingService(),
            settings=settings,
        )
