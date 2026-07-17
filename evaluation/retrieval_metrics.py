from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from statistics import median
from typing import Any

from evaluation.retrieval_benchmark import BenchmarkCase

_TEXT_KEYS = ("content", "text", "snippet", "chunk_text", "page_content")
_ID_KEYS = ("id", "chunk_id", "document_chunk_id")
_SCORE_KEYS = (
    "score",
    "combined_score",
    "similarity",
    "rank_score",
    "rrf_score",
)


@dataclass(frozen=True, slots=True)
class NormalizedResult:
    rank: int
    result_id: str
    text: str
    page_start: int | None
    page_end: int | None
    score: float | None
    document_title: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if not 0.0 <= percentile_value <= 1.0:
        raise ValueError("percentile_value must be between 0 and 1.")

    ordered = sorted(values)
    index = max(
        0,
        min(
            len(ordered) - 1,
            int((len(ordered) * percentile_value) + 0.999999) - 1,
        ),
    )
    return ordered[index]


def _first_value(
    item: dict[str, Any],
    metadata: dict[str, Any],
    keys: Iterable[str],
) -> Any:
    for key in keys:
        if item.get(key) is not None:
            return item[key]
        if metadata.get(key) is not None:
            return metadata[key]
    return None


def _to_optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_result(item: Any, rank: int) -> NormalizedResult:
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    elif hasattr(item, "__dict__") and not isinstance(item, dict):
        item = vars(item)

    if not isinstance(item, dict):
        item = {"text": str(item)}

    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    text_value = _first_value(item, metadata, _TEXT_KEYS)
    result_id = _first_value(item, metadata, _ID_KEYS)
    score = _first_value(item, metadata, _SCORE_KEYS)

    page_start = _to_optional_int(
        _first_value(
            item,
            metadata,
            ("page_start", "start_page", "page_number", "page"),
        )
    )
    page_end = _to_optional_int(
        _first_value(
            item,
            metadata,
            ("page_end", "end_page", "page_number", "page"),
        )
    )

    if page_start is not None and page_end is None:
        page_end = page_start
    if page_end is not None and page_start is None:
        page_start = page_end

    document_title = _first_value(
        item,
        metadata,
        ("document_title", "title", "source_title"),
    )

    return NormalizedResult(
        rank=rank,
        result_id=str(result_id or f"rank-{rank}"),
        text=str(text_value or ""),
        page_start=page_start,
        page_end=page_end,
        score=_to_optional_float(score),
        document_title=(str(document_title) if document_title not in (None, "") else None),
    )


def normalize_results(items: Iterable[Any]) -> list[NormalizedResult]:
    return [normalize_result(item, rank=index) for index, item in enumerate(items, start=1)]


def _matched_term_groups(
    result: NormalizedResult,
    case: BenchmarkCase,
) -> list[int]:
    lowered = result.text.lower()
    matched: list[int] = []

    for index, group in enumerate(case.required_term_groups):
        if any(term in lowered for term in group):
            matched.append(index)

    return matched


def _page_matches(
    result: NormalizedResult,
    case: BenchmarkCase,
) -> list[int]:
    return [
        index
        for index, page_range in enumerate(case.expected_page_ranges)
        if page_range.overlaps(result.page_start, result.page_end)
    ]


def judge_result(
    result: NormalizedResult,
    case: BenchmarkCase,
) -> dict[str, Any]:
    page_matches = _page_matches(result, case)
    term_matches = _matched_term_groups(result, case)

    page_relevant = bool(page_matches) if case.expected_page_ranges else True
    term_relevant = (
        len(term_matches) >= case.minimum_term_groups if case.required_term_groups else True
    )

    return {
        "relevant": page_relevant and term_relevant,
        "page_relevant": page_relevant,
        "term_relevant": term_relevant,
        "page_target_matches": page_matches,
        "term_group_matches": term_matches,
    }


def evaluate_query(
    case: BenchmarkCase,
    results: list[NormalizedResult],
    *,
    top_k: int,
    latency_samples_ms: list[float] | None = None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    limited = results[:top_k]
    judged: list[dict[str, Any]] = []

    for result in limited:
        judgment = judge_result(result, case)
        judged.append(
            {
                **result.to_dict(),
                **judgment,
                "snippet": result.text[:600],
            }
        )

    relevant_ranks = [item["rank"] for item in judged if item["relevant"]]
    first_relevant_rank = relevant_ranks[0] if relevant_ranks else None
    reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0

    def precision_at(cutoff: int) -> float:
        relevant_count = sum(1 for item in judged[:cutoff] if item["relevant"])
        return relevant_count / cutoff

    page_targets_hit: set[int] = set()
    term_targets_hit: set[int] = set()

    for item in judged[:5]:
        if not item["relevant"]:
            continue
        page_targets_hit.update(item["page_target_matches"])
        term_targets_hit.update(item["term_group_matches"])

    target_count = len(case.expected_page_ranges) + len(case.required_term_groups)
    targets_hit = len(page_targets_hit) + len(term_targets_hit)
    evidence_recall_at_5 = targets_hit / target_count if target_count else 0.0

    raw_latency_samples = list(latency_samples_ms or [])
    if not raw_latency_samples and latency_ms is not None:
        raw_latency_samples = [latency_ms]

    latency_samples = [round(value, 3) for value in raw_latency_samples]
    median_latency = median(raw_latency_samples) if raw_latency_samples else 0.0
    p95_latency = percentile(raw_latency_samples, 0.95)

    return {
        "case_id": case.id,
        "query": case.query,
        "annotation_status": case.annotation_status,
        "latency_samples_ms": latency_samples,
        "median_latency_ms": round(median_latency, 3),
        "p95_latency_ms": round(p95_latency, 3),
        "returned_count": len(limited),
        "first_relevant_rank": first_relevant_rank,
        "reciprocal_rank": round(reciprocal_rank, 6),
        "hit_at_1": bool(relevant_ranks and relevant_ranks[0] <= 1),
        "hit_at_3": bool(relevant_ranks and relevant_ranks[0] <= 3),
        "hit_at_5": bool(relevant_ranks and relevant_ranks[0] <= 5),
        "precision_at_3": round(precision_at(3), 6),
        "evidence_recall_at_5": round(
            evidence_recall_at_5,
            6,
        ),
        "results": judged,
    }


def aggregate_method(
    method: str,
    query_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    if not query_reports:
        return {
            "method": method,
            "query_count": 0,
            "mean_reciprocal_rank": 0.0,
            "hit_rate_at_1": 0.0,
            "hit_rate_at_3": 0.0,
            "mean_precision_at_3": 0.0,
            "mean_evidence_recall_at_5": 0.0,
            "mean_latency_ms": 0.0,
            "median_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
        }

    count = len(query_reports)

    def mean(key: str) -> float:
        return sum(float(item[key]) for item in query_reports) / count

    all_latency_samples: list[float] = []
    for item in query_reports:
        samples = item.get("latency_samples_ms", [])
        if samples:
            all_latency_samples.extend(float(sample) for sample in samples)
        elif item.get("median_latency_ms") is not None:
            all_latency_samples.append(float(item["median_latency_ms"]))
        elif item.get("latency_ms") is not None:
            all_latency_samples.append(float(item["latency_ms"]))

    return {
        "method": method,
        "query_count": count,
        "mean_reciprocal_rank": round(
            mean("reciprocal_rank"),
            6,
        ),
        "hit_rate_at_1": round(
            sum(bool(item["hit_at_1"]) for item in query_reports) / count,
            6,
        ),
        "hit_rate_at_3": round(
            sum(bool(item["hit_at_3"]) for item in query_reports) / count,
            6,
        ),
        "mean_precision_at_3": round(
            mean("precision_at_3"),
            6,
        ),
        "mean_evidence_recall_at_5": round(
            mean("evidence_recall_at_5"),
            6,
        ),
        "mean_latency_ms": round(
            (sum(all_latency_samples) / len(all_latency_samples) if all_latency_samples else 0.0),
            3,
        ),
        "median_latency_ms": round(
            median(all_latency_samples) if all_latency_samples else 0.0,
            3,
        ),
        "p95_latency_ms": round(
            percentile(all_latency_samples, 0.95),
            3,
        ),
    }
