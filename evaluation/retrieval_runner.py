from __future__ import annotations

import importlib
import inspect
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evaluation.retrieval_benchmark import (
    RetrievalBenchmark,
    load_benchmark,
)
from evaluation.retrieval_metrics import (
    aggregate_method,
    evaluate_query,
    normalize_results,
)

RETRIEVER_CLASSES = {
    "lexical": (
        "evaluation.hosted_retriever",
        "HostedRetrievalAdapter",
    ),
    "semantic": (
        "evaluation.hosted_retriever",
        "HostedRetrievalAdapter",
    ),
    "hybrid": (
        "evaluation.hosted_retriever",
        "HostedRetrievalAdapter",
    ),
    "hybrid_reranked": (
        "evaluation.reranked_retriever",
        "RerankedHostedRetriever",
    ),
}


def _load_retriever(method: str) -> Any:
    if method not in RETRIEVER_CLASSES:
        raise ValueError(f"Unsupported retrieval method: {method}")

    module_name, class_name = RETRIEVER_CLASSES[method]
    module = importlib.import_module(module_name)
    retriever_class = getattr(module, class_name)
    if method == "hybrid_reranked":
        return retriever_class()
    return retriever_class(method=method)


def _extract_items(payload: Any) -> list[Any]:
    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if isinstance(payload, tuple):
        return list(payload)

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    if isinstance(payload, dict):
        for key in (
            "results",
            "matches",
            "data",
            "items",
            "documents",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    if hasattr(payload, "results"):
        value = payload.results
        if isinstance(value, list):
            return value

    raise TypeError(
        "Retriever returned an unsupported payload. Expected a list "
        "or a mapping containing results/matches/data/items/documents."
    )


def _build_search_call(
    search_method: Any,
    *,
    query: str,
    top_k: int,
    document_id: str | None,
) -> tuple[list[Any], dict[str, Any]]:
    signature = inspect.signature(search_method)
    parameters = signature.parameters

    args: list[Any] = []
    kwargs: dict[str, Any] = {}

    if "query" in parameters:
        kwargs["query"] = query
    elif "search_query" in parameters:
        kwargs["search_query"] = query
    else:
        args.append(query)

    for name in (
        "top_k",
        "limit",
        "match_count",
        "num_results",
        "k",
    ):
        if name in parameters:
            kwargs[name] = top_k
            break

    if document_id:
        if "document_id" in parameters:
            kwargs["document_id"] = document_id
        elif "manifest_id" in parameters:
            kwargs["manifest_id"] = document_id
        elif "filters" in parameters:
            kwargs["filters"] = {"document_id": document_id}
        elif "filter" in parameters:
            kwargs["filter"] = {"document_id": document_id}

    return args, kwargs


async def _invoke_search(
    retriever: Any,
    *,
    query: str,
    top_k: int,
    document_id: str | None,
) -> list[Any]:
    search_method = getattr(retriever, "search", None)
    if search_method is None:
        raise AttributeError(f"{type(retriever).__name__} does not provide search().")

    args, kwargs = _build_search_call(
        search_method,
        query=query,
        top_k=top_k,
        document_id=document_id,
    )
    payload = search_method(*args, **kwargs)

    if inspect.isawaitable(payload):
        payload = await payload

    return _extract_items(payload)


def _ranking_signature(results: list[Any]) -> list[str]:
    normalized = normalize_results(results)
    return [item.result_id for item in normalized]


async def _warm_retriever(
    retriever: Any,
    *,
    query: str,
    top_k: int,
    document_id: str | None,
    warmup_count: int,
) -> None:
    for _ in range(warmup_count):
        results = await _invoke_search(
            retriever,
            query=query,
            top_k=top_k,
            document_id=document_id,
        )
        if not results:
            raise RuntimeError("Warm-up retrieval returned no results.")


async def run_benchmark(
    benchmark_path: Path,
    *,
    methods: list[str],
    top_k: int = 5,
    document_id: str | None = None,
    repetitions: int = 3,
    warmup_count: int = 1,
) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1.")
    if warmup_count < 0:
        raise ValueError("warmup_count cannot be negative.")

    benchmark: RetrievalBenchmark = load_benchmark(benchmark_path)
    effective_document_id = document_id or benchmark.document_id

    report: dict[str, Any] = {
        "benchmark": {
            "version": benchmark.version,
            "name": benchmark.name,
            "description": benchmark.description,
            "document_id": effective_document_id,
            "case_count": len(benchmark.cases),
            "top_k": top_k,
            "repetitions": repetitions,
            "warmup_count": warmup_count,
            "relevance_rule": ("page_overlap AND minimum_term_groups"),
        },
        "methods": {},
        "summary": [],
        "errors": [],
    }

    for method in methods:
        try:
            retriever = _load_retriever(method)
        except Exception as exc:
            report["errors"].append(
                {
                    "method": method,
                    "stage": "initialization",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue

        if warmup_count:
            try:
                await _warm_retriever(
                    retriever,
                    query=benchmark.cases[0].query,
                    top_k=top_k,
                    document_id=effective_document_id,
                    warmup_count=warmup_count,
                )
            except Exception as exc:
                report["errors"].append(
                    {
                        "method": method,
                        "stage": "warmup",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                report["methods"][method] = []
                report["summary"].append(aggregate_method(method, []))
                continue

        query_reports: list[dict[str, Any]] = []

        for case in benchmark.cases:
            latency_samples_ms: list[float] = []
            result_sets: list[list[Any]] = []

            try:
                for _ in range(repetitions):
                    started = time.perf_counter()
                    raw_results = await _invoke_search(
                        retriever,
                        query=case.query,
                        top_k=top_k,
                        document_id=effective_document_id,
                    )
                    latency_samples_ms.append((time.perf_counter() - started) * 1000)

                    if not raw_results:
                        raise RuntimeError(
                            f"{method} retrieval returned no "
                            f"results for benchmark case "
                            f"{case.id!r}."
                        )
                    result_sets.append(raw_results)

                signatures = [_ranking_signature(results) for results in result_sets]
                normalized = normalize_results(result_sets[0])
                query_report = evaluate_query(
                    case,
                    normalized,
                    latency_samples_ms=latency_samples_ms,
                    top_k=top_k,
                )
                query_report["ranking_stable"] = all(
                    signature == signatures[0] for signature in signatures[1:]
                )
                query_report["ranking_signatures"] = signatures
                query_reports.append(query_report)
            except Exception as exc:
                report["errors"].append(
                    {
                        "method": method,
                        "case_id": case.id,
                        "query": case.query,
                        "stage": "search",
                        "latency_samples_ms": [round(value, 3) for value in latency_samples_ms],
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )

        report["methods"][method] = query_reports
        report["summary"].append(aggregate_method(method, query_reports))

    report["benchmark_cases"] = [
        {
            **asdict(case),
            "expected_page_ranges": [
                asdict(page_range) for page_range in (case.expected_page_ranges)
            ],
        }
        for case in benchmark.cases
    ]
    return report
