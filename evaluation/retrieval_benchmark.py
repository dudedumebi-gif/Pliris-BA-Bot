from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PageRange:
    start: int
    end: int

    def overlaps(self, page_start: int | None, page_end: int | None) -> bool:
        if page_start is None or page_end is None:
            return False
        return page_start <= self.end and page_end >= self.start


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    id: str
    query: str
    expected_page_ranges: tuple[PageRange, ...]
    required_term_groups: tuple[tuple[str, ...], ...]
    minimum_term_groups: int
    annotation_status: str


@dataclass(frozen=True, slots=True)
class RetrievalBenchmark:
    version: int
    name: str
    document_id: str
    description: str
    cases: tuple[BenchmarkCase, ...]


def _build_case(raw: dict[str, Any]) -> BenchmarkCase:
    case_id = str(raw.get("id", "")).strip()
    query = str(raw.get("query", "")).strip()

    if not case_id:
        raise ValueError("Every benchmark case requires a non-empty id.")
    if not query:
        raise ValueError(f"Benchmark case {case_id!r} requires a query.")

    page_ranges: list[PageRange] = []
    for item in raw.get("expected_page_ranges", []):
        start = int(item["start"])
        end = int(item["end"])
        if start < 1 or end < start:
            raise ValueError(f"Invalid page range {start}-{end} for case {case_id!r}.")
        page_ranges.append(PageRange(start=start, end=end))

    term_groups: list[tuple[str, ...]] = []
    for group in raw.get("required_term_groups", []):
        normalized = tuple(str(term).strip().lower() for term in group if str(term).strip())
        if normalized:
            term_groups.append(normalized)

    if not page_ranges and not term_groups:
        raise ValueError(f"Benchmark case {case_id!r} requires pages or term groups.")

    minimum_term_groups = int(raw.get("minimum_term_groups", 1))
    if term_groups:
        if minimum_term_groups < 1:
            raise ValueError(f"minimum_term_groups must be positive for {case_id!r}.")
        minimum_term_groups = min(minimum_term_groups, len(term_groups))
    else:
        minimum_term_groups = 0

    return BenchmarkCase(
        id=case_id,
        query=query,
        expected_page_ranges=tuple(page_ranges),
        required_term_groups=tuple(term_groups),
        minimum_term_groups=minimum_term_groups,
        annotation_status=str(raw.get("annotation_status", "unreviewed")).strip(),
    )


def load_benchmark(path: Path) -> RetrievalBenchmark:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", [])
    cases = tuple(_build_case(item) for item in raw_cases)

    if not cases:
        raise ValueError("The retrieval benchmark contains no cases.")

    identifiers = [case.id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Benchmark case ids must be unique.")

    return RetrievalBenchmark(
        version=int(payload.get("version", 1)),
        name=str(payload.get("name", "Retrieval Benchmark")),
        document_id=str(payload.get("document_id", "")).strip(),
        description=str(payload.get("description", "")).strip(),
        cases=cases,
    )
