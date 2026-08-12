from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.llm_contexts import (
    ContextFreezeError,
    MeteredEmbeddingService,
    context_fingerprint,
    freeze_contexts,
    load_frozen_contexts,
    write_frozen_contexts,
)
from evaluation.llm_contract import load_evaluation_contract
from pliris.retrieval.models import RetrievedChunk

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeEmbeddingService:
    def embed_texts(self, texts, **kwargs):
        return SimpleNamespace(
            embeddings=[[0.1, 0.2]],
            input_tokens=len(texts) * 7,
        )


class BenchmarkRetriever:
    def __init__(self, contract, *, weak: bool = False):
        self.contract = contract
        self.weak = weak
        self.calls = []

    async def search(
        self,
        query,
        *,
        top_k,
        document_id,
    ):
        self.calls.append((query, top_k, document_id))
        case = next(item for item in self.contract.benchmark.cases if item.retrieval_query == query)
        if self.weak:
            return [
                RetrievedChunk(
                    rank=1,
                    chunk_id=f"{case.id}-weak",
                    text="Unrelated material.",
                    title="Weak",
                    source="weak",
                    page_start=999,
                    page_end=999,
                    score=0.1,
                    document_id="doc",
                    metadata={},
                )
            ]

        text = " ".join(group[0] for group in case.required_term_groups)
        page = case.expected_page_ranges[0]
        return [
            RetrievedChunk(
                rank=1,
                chunk_id=f"{case.id}-1",
                text=text,
                title="Benchmark source",
                source="benchmark",
                page_start=page.start,
                page_end=page.end,
                score=1.0,
                document_id="doc",
                metadata={},
            )
        ]


def contract():
    return load_evaluation_contract(REPO_ROOT)


def test_metered_embedding_service_accumulates_tokens() -> None:
    meter = MeteredEmbeddingService(FakeEmbeddingService())

    meter.embed_texts(["a", "b"])
    meter.embed_texts(["c"])

    assert meter.input_tokens == 21


@pytest.mark.asyncio
async def test_freezes_each_retrieval_case_once_and_covers_all_strategies() -> None:
    active = contract()
    retriever = BenchmarkRetriever(active)

    bundle = await freeze_contexts(
        active,
        retriever=retriever,
        embedding_usage_provider=lambda: 25,
        embedding_price_per_million=0.02,
    )

    retrieval_count = sum(
        case.context_strategy.value == "retrieval" for case in active.benchmark.cases
    )
    assert len(retriever.calls) == retrieval_count
    assert len(bundle.records) == 12
    assert {record.context_strategy.value for record in bundle.records} == {
        "retrieval",
        "synthetic",
        "empty",
    }
    assert all(record.quality.passed for record in bundle.records)
    assert bundle.manifest.embedding_input_tokens == 25


@pytest.mark.asyncio
async def test_frozen_context_round_trip_preserves_fingerprints(
    tmp_path: Path,
) -> None:
    active = contract()
    bundle = await freeze_contexts(
        active,
        retriever=BenchmarkRetriever(active),
    )
    path = tmp_path / "frozen.jsonl"

    write_frozen_contexts(path, bundle)
    loaded = load_frozen_contexts(path, active)

    assert loaded.manifest.case_count == 12
    assert [record.context_fingerprint for record in loaded.records] == [
        record.context_fingerprint for record in bundle.records
    ]
    assert all(
        context_fingerprint(record) == record.context_fingerprint for record in loaded.records
    )


@pytest.mark.asyncio
async def test_rejects_weak_retrieval_context_before_generation() -> None:
    active = contract()

    with pytest.raises(
        ContextFreezeError,
        match="Context quality gate failed",
    ):
        await freeze_contexts(
            active,
            retriever=BenchmarkRetriever(
                active,
                weak=True,
            ),
        )


@pytest.mark.asyncio
async def test_rejects_tampered_context_fingerprint(
    tmp_path: Path,
) -> None:
    active = contract()
    bundle = await freeze_contexts(
        active,
        retriever=BenchmarkRetriever(active),
    )
    path = tmp_path / "frozen.jsonl"
    write_frozen_contexts(path, bundle)

    lines = path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[1])
    payload["context_text"] += " tampered"
    lines[1] = json.dumps(payload)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(
        ContextFreezeError,
        match="failed fingerprint validation",
    ):
        load_frozen_contexts(path, active)
