from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from evaluation.local_reranker import (
    LocalCrossEncoderReranker,
    RerankerConfig,
)
from evaluation.reranked_retriever import RerankedHostedRetriever
from evaluation.retrieval_runner import _load_retriever


class FakeCrossEncoder:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.calls: list[tuple[list[tuple[str, str]], int, bool, bool]] = []

    def predict(
        self,
        sentences: list[tuple[str, str]],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
    ) -> list[float]:
        self.calls.append(
            (
                list(sentences),
                batch_size,
                show_progress_bar,
                convert_to_numpy,
            )
        )
        return self.scores


class FakeHostedRetriever:
    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "filters": filters,
                "document_id": document_id,
            }
        )
        return self.results[:top_k]


def candidate(
    result_id: str,
    text: str,
    score: float,
    page_start: int,
) -> dict[str, Any]:
    return {
        "id": result_id,
        "text": text,
        "score": score,
        "page_start": page_start,
        "page_end": page_start + 1,
        "metadata": {"source": "BABOK"},
    }


def test_local_reranker_promotes_highest_cross_encoder_score() -> None:
    model = FakeCrossEncoder([0.1, 0.9, 0.4])
    reranker = LocalCrossEncoderReranker(
        RerankerConfig(batch_size=8),
        model_factory=lambda: model,
    )
    results = [
        candidate("a", "General introduction.", 0.9, 10),
        candidate(
            "b",
            "Business analysis is the practice of enabling change.",
            0.8,
            12,
        ),
        candidate("c", "Stakeholder planning.", 0.7, 40),
    ]

    reranked = reranker.rerank(
        "What is business analysis?",
        results,
        top_k=2,
    )

    assert [item["id"] for item in reranked] == ["b", "c"]
    assert reranked[0]["retrieval_score"] == pytest.approx(0.8)
    assert reranked[0]["rerank_score"] == pytest.approx(0.9)
    assert reranked[0]["original_rank"] == 2
    assert reranked[0]["metadata"]["reranker_model"].endswith("MiniLM-L6-v2")
    assert model.calls[0][1:] == (8, False, True)


def test_local_reranker_loads_model_once() -> None:
    model = FakeCrossEncoder([0.5])
    factory_calls = 0

    def factory() -> FakeCrossEncoder:
        nonlocal factory_calls
        factory_calls += 1
        return model

    reranker = LocalCrossEncoderReranker(
        model_factory=factory,
    )
    results = [candidate("a", "Definition.", 0.3, 12)]

    reranker.rerank("query one", results, top_k=1)
    reranker.rerank("query two", results, top_k=1)

    assert factory_calls == 1
    assert len(model.calls) == 2


def test_local_reranker_rejects_score_count_mismatch() -> None:
    reranker = LocalCrossEncoderReranker(
        model_factory=lambda: FakeCrossEncoder([0.5]),
    )
    results = [
        candidate("a", "First.", 0.3, 12),
        candidate("b", "Second.", 0.2, 13),
    ]

    with pytest.raises(
        RuntimeError,
        match="different number of scores",
    ):
        reranker.rerank("query", results, top_k=2)


@pytest.mark.asyncio
async def test_reranked_retriever_fetches_wider_candidate_pool() -> None:
    candidates = [
        candidate(
            str(index),
            f"Candidate {index}",
            float(30 - index),
            index,
        )
        for index in range(30)
    ]
    base = FakeHostedRetriever(candidates)
    model = FakeCrossEncoder([float(index) for index in range(20)])
    reranker = LocalCrossEncoderReranker(
        model_factory=lambda: model,
    )
    retriever = RerankedHostedRetriever(
        base_retriever=base,
        reranker=reranker,
        candidate_multiplier=4,
        minimum_candidates=20,
    )

    results = await retriever.search(
        "What is requirements validation?",
        top_k=5,
        document_id="babok-v3",
    )

    assert base.calls == [
        {
            "query": "What is requirements validation?",
            "top_k": 20,
            "filters": None,
            "document_id": "babok-v3",
        }
    ]
    assert len(results) == 5
    assert [item["id"] for item in results] == [
        "19",
        "18",
        "17",
        "16",
        "15",
    ]


@pytest.mark.asyncio
async def test_reranked_retriever_returns_empty_candidates() -> None:
    base = FakeHostedRetriever([])
    reranker = LocalCrossEncoderReranker(
        model_factory=lambda: FakeCrossEncoder([]),
    )
    retriever = RerankedHostedRetriever(
        base_retriever=base,
        reranker=reranker,
    )

    results = await retriever.search("query", top_k=5)

    assert results == []


def test_runner_loads_reranked_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = SimpleNamespace(name="reranked")

    class FakeRetriever:
        def __init__(self) -> None:
            self.value = sentinel

    monkeypatch.setattr(
        "evaluation.retrieval_runner.importlib.import_module",
        lambda _name: SimpleNamespace(RerankedHostedRetriever=FakeRetriever),
    )

    loaded = _load_retriever("hybrid_reranked")

    assert loaded.value is sentinel
