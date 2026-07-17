from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.retrieval_benchmark import BenchmarkCase, PageRange, load_benchmark
from evaluation.retrieval_metrics import (
    NormalizedResult,
    aggregate_method,
    evaluate_query,
    judge_result,
    normalize_result,
    percentile,
)
from evaluation.retrieval_runner import (
    _build_search_call,
    _extract_items,
    run_benchmark,
)


def make_case() -> BenchmarkCase:
    return BenchmarkCase(
        id="traceability",
        query="What is requirements traceability?",
        expected_page_ranges=(PageRange(89, 93),),
        required_term_groups=(
            ("lineage",),
            ("backward traceability", "forward traceability"),
        ),
        minimum_term_groups=2,
        annotation_status="page_verified",
    )


def make_result(
    *,
    text: str,
    page_start: int,
    page_end: int,
    rank: int = 1,
) -> NormalizedResult:
    return NormalizedResult(
        rank=rank,
        result_id=f"chunk-{rank}",
        text=text,
        page_start=page_start,
        page_end=page_end,
        score=0.5,
        document_title="BABOK",
    )


def test_load_benchmark_validates_and_normalizes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "benchmark.json"
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Test",
                "document_id": "babok-v3",
                "cases": [
                    {
                        "id": "definition",
                        "query": "What is business analysis?",
                        "expected_page_ranges": [{"start": 12, "end": 14}],
                        "required_term_groups": [["Practice of Enabling Change"]],
                        "minimum_term_groups": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    benchmark = load_benchmark(path)

    assert benchmark.document_id == "babok-v3"
    assert benchmark.cases[0].expected_page_ranges[0] == PageRange(
        12,
        14,
    )
    assert benchmark.cases[0].required_term_groups == (("practice of enabling change",),)


def test_normalize_result_reads_nested_metadata() -> None:
    normalized = normalize_result(
        {
            "chunk_id": "chunk-1",
            "content": "Requirements traceability identifies lineage.",
            "combined_score": "0.75",
            "metadata": {
                "page_start": 89,
                "page_end": 93,
                "document_title": "BABOK",
            },
        },
        rank=1,
    )

    assert normalized.result_id == "chunk-1"
    assert normalized.page_start == 89
    assert normalized.page_end == 93
    assert normalized.score == pytest.approx(0.75)
    assert normalized.document_title == "BABOK"


def test_page_overlap_without_terms_is_not_relevant() -> None:
    judgment = judge_result(
        make_result(
            text="Unrelated excerpt beginning at a figure.",
            page_start=90,
            page_end=92,
        ),
        make_case(),
    )

    assert judgment["page_relevant"] is True
    assert judgment["term_relevant"] is False
    assert judgment["relevant"] is False


def test_terms_without_page_overlap_are_not_relevant() -> None:
    judgment = judge_result(
        make_result(
            text=(
                "Traceability records lineage and supports backward "
                "traceability and forward traceability."
            ),
            page_start=200,
            page_end=201,
        ),
        make_case(),
    )

    assert judgment["page_relevant"] is False
    assert judgment["term_relevant"] is True
    assert judgment["relevant"] is False


def test_page_overlap_and_terms_are_relevant() -> None:
    judgment = judge_result(
        make_result(
            text=(
                "Traceability records lineage and supports backward "
                "traceability and forward traceability."
            ),
            page_start=89,
            page_end=91,
        ),
        make_case(),
    )

    assert judgment["page_relevant"] is True
    assert judgment["term_relevant"] is True
    assert judgment["relevant"] is True


def test_evaluate_query_calculates_strict_rank_metrics() -> None:
    report = evaluate_query(
        make_case(),
        [
            make_result(
                text="Sequence diagram lifeline.",
                page_start=90,
                page_end=92,
                rank=1,
            ),
            make_result(
                text=(
                    "Traceability records lineage and supports backward "
                    "traceability and forward traceability."
                ),
                page_start=89,
                page_end=91,
                rank=2,
            ),
        ],
        latency_ms=10.0,
        top_k=5,
    )

    assert report["first_relevant_rank"] == 2
    assert report["reciprocal_rank"] == pytest.approx(0.5)
    assert report["hit_at_1"] is False
    assert report["hit_at_3"] is True
    assert report["precision_at_3"] == pytest.approx(1 / 3)


def test_evidence_recall_ignores_nonrelevant_page_hits() -> None:
    report = evaluate_query(
        make_case(),
        [
            make_result(
                text="General diagram content.",
                page_start=89,
                page_end=91,
                rank=1,
            ),
            make_result(
                text=(
                    "Traceability records lineage and supports backward "
                    "traceability and forward traceability."
                ),
                page_start=89,
                page_end=91,
                rank=2,
            ),
        ],
        latency_samples_ms=[100.0, 110.0, 120.0],
        top_k=5,
    )

    assert report["first_relevant_rank"] == 2
    assert report["evidence_recall_at_5"] == pytest.approx(1.0)
    assert report["median_latency_ms"] == pytest.approx(110.0)
    assert report["p95_latency_ms"] == pytest.approx(120.0)


def test_aggregate_method_preserves_legacy_latency_input() -> None:
    reports = [
        {
            "reciprocal_rank": 1.0,
            "hit_at_1": True,
            "hit_at_3": True,
            "precision_at_3": 2 / 3,
            "evidence_recall_at_5": 1.0,
            "latency_ms": 100.0,
        },
        {
            "reciprocal_rank": 0.5,
            "hit_at_1": False,
            "hit_at_3": True,
            "precision_at_3": 1 / 3,
            "evidence_recall_at_5": 0.5,
            "latency_ms": 200.0,
        },
    ]

    summary = aggregate_method("hybrid", reports)

    assert summary["mean_reciprocal_rank"] == pytest.approx(0.75)
    assert summary["hit_rate_at_1"] == pytest.approx(0.5)
    assert summary["mean_latency_ms"] == pytest.approx(150.0)


def test_aggregate_method_reports_latency_distribution() -> None:
    reports = [
        {
            "reciprocal_rank": 1.0,
            "hit_at_1": True,
            "hit_at_3": True,
            "precision_at_3": 1.0,
            "evidence_recall_at_5": 1.0,
            "latency_samples_ms": [100.0, 200.0, 300.0],
        },
        {
            "reciprocal_rank": 0.5,
            "hit_at_1": False,
            "hit_at_3": True,
            "precision_at_3": 2 / 3,
            "evidence_recall_at_5": 0.5,
            "latency_samples_ms": [400.0, 500.0, 600.0],
        },
    ]

    summary = aggregate_method("hybrid", reports)

    assert summary["mean_latency_ms"] == pytest.approx(350.0)
    assert summary["median_latency_ms"] == pytest.approx(350.0)
    assert summary["p95_latency_ms"] == pytest.approx(600.0)


def test_percentile_uses_nearest_rank() -> None:
    samples = [100.0, 200.0, 300.0, 400.0, 500.0]

    assert percentile(samples, 0.5) == pytest.approx(300.0)
    assert percentile(samples, 0.95) == pytest.approx(500.0)


def test_extract_items_accepts_common_payload_shapes() -> None:
    assert _extract_items([{"id": 1}]) == [{"id": 1}]
    assert _extract_items({"results": [{"id": 2}]}) == [{"id": 2}]
    assert _extract_items({"data": [{"id": 3}]}) == [{"id": 3}]


def test_build_search_call_adapts_common_parameter_names() -> None:
    async def search(
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        return []

    args, kwargs = _build_search_call(
        search,
        query="test",
        top_k=10,
        document_id="babok-v3",
    )

    assert args == []
    assert kwargs == {
        "query": "test",
        "top_k": 10,
        "filters": {"document_id": "babok-v3"},
    }


@pytest.mark.asyncio
async def test_benchmark_records_empty_retrieval_as_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Test Benchmark",
                "document_id": "babok-v3",
                "cases": [
                    {
                        "id": "definition",
                        "query": "What is business analysis?",
                        "expected_page_ranges": [{"start": 12, "end": 14}],
                        "required_term_groups": [["business analysis"]],
                        "minimum_term_groups": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class EmptyRetriever:
        async def search(
            self,
            query: str,
            top_k: int = 5,
            filters: dict | None = None,
        ) -> list[dict]:
            return []

    monkeypatch.setattr(
        "evaluation.retrieval_runner._load_retriever",
        lambda _method: EmptyRetriever(),
    )

    report = await run_benchmark(
        benchmark_path,
        methods=["lexical"],
        top_k=5,
        repetitions=1,
        warmup_count=0,
    )

    assert report["methods"]["lexical"] == []
    assert len(report["errors"]) == 1
    assert report["errors"][0]["stage"] == "search"
    assert "returned no results" in report["errors"][0]["message"]


@pytest.mark.asyncio
async def test_runner_warms_and_repeats_each_query(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Test",
                "document_id": "babok-v3",
                "cases": [
                    {
                        "id": "definition",
                        "query": "What is business analysis?",
                        "expected_page_ranges": [{"start": 12, "end": 14}],
                        "required_term_groups": [
                            ["practice of enabling change"],
                            ["deliver value"],
                        ],
                        "minimum_term_groups": 2,
                        "annotation_status": "page_verified",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class StableRetriever:
        def __init__(self) -> None:
            self.calls = 0

        async def search(
            self,
            query: str,
            top_k: int = 5,
            document_id: str | None = None,
        ) -> list[dict]:
            self.calls += 1
            return [
                {
                    "id": "chunk-1",
                    "text": (
                        "Business analysis is the practice of enabling "
                        "change and helps deliver value."
                    ),
                    "page_start": 12,
                    "page_end": 14,
                    "score": 0.5,
                }
            ]

    retriever = StableRetriever()
    monkeypatch.setattr(
        "evaluation.retrieval_runner._load_retriever",
        lambda _method: retriever,
    )

    report = await run_benchmark(
        benchmark_path,
        methods=["hybrid"],
        top_k=5,
        repetitions=3,
        warmup_count=1,
    )

    query_report = report["methods"]["hybrid"][0]

    assert retriever.calls == 4
    assert len(query_report["latency_samples_ms"]) == 3
    assert query_report["ranking_stable"] is True
    assert report["errors"] == []
