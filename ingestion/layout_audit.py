from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz

_WHITESPACE_RE = re.compile(r"\s+")
_DIGIT_RE = re.compile(r"\d+")


@dataclass(slots=True)
class TextBlock:
    page_number: int
    block_number: int
    text: str
    normalized_text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float
    location: str


@dataclass(slots=True)
class RepeatedBlockCandidate:
    normalized_text: str
    sample_text: str
    page_count: int
    page_ratio: float
    locations: dict[str, int]
    sample_pages: list[int]
    reasons: list[str]


def normalize_block_text(text: str) -> str:
    normalized = _WHITESPACE_RE.sub(" ", text).strip().lower()
    return _DIGIT_RE.sub("<n>", normalized)


def classify_location(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    page_width: float,
    page_height: float,
    *,
    edge_ratio: float = 0.12,
) -> str:
    top_limit = page_height * edge_ratio
    bottom_limit = page_height * (1 - edge_ratio)
    left_limit = page_width * edge_ratio
    right_limit = page_width * (1 - edge_ratio)

    if y1 <= top_limit:
        return "top"
    if y0 >= bottom_limit:
        return "bottom"
    if x1 <= left_limit:
        return "left"
    if x0 >= right_limit:
        return "right"
    return "body"


def extract_text_blocks(
    pdf_path: Path,
    *,
    max_pages: int | None = None,
) -> tuple[list[TextBlock], int]:
    blocks: list[TextBlock] = []

    with fitz.open(pdf_path) as document:
        total_pages = document.page_count
        pages_to_read = min(total_pages, max_pages) if max_pages else total_pages

        for page_index in range(pages_to_read):
            page = document.load_page(page_index)
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)

            for item in page.get_text("blocks", sort=True):
                if len(item) < 5:
                    continue

                x0, y0, x1, y1 = map(float, item[:4])
                text = str(item[4]).strip()
                block_number = int(item[5]) if len(item) > 5 else len(blocks)

                if not text:
                    continue

                normalized = normalize_block_text(text)
                if not normalized:
                    continue

                blocks.append(
                    TextBlock(
                        page_number=page_index + 1,
                        block_number=block_number,
                        text=text,
                        normalized_text=normalized,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                        page_width=page_width,
                        page_height=page_height,
                        location=classify_location(
                            x0,
                            y0,
                            x1,
                            y1,
                            page_width,
                            page_height,
                        ),
                    )
                )

    return blocks, total_pages


def find_repeated_candidates(
    blocks: list[TextBlock],
    *,
    total_pages: int,
    minimum_pages: int = 5,
    minimum_page_ratio: float = 0.02,
) -> list[RepeatedBlockCandidate]:
    pages_by_text: dict[str, set[int]] = defaultdict(set)
    samples: dict[str, str] = {}
    locations: dict[str, Counter[str]] = defaultdict(Counter)

    for block in blocks:
        pages_by_text[block.normalized_text].add(block.page_number)
        samples.setdefault(block.normalized_text, block.text)
        locations[block.normalized_text][block.location] += 1

    candidates: list[RepeatedBlockCandidate] = []

    for normalized_text, pages in pages_by_text.items():
        page_count = len(pages)
        page_ratio = page_count / max(total_pages, 1)

        if page_count < minimum_pages or page_ratio < minimum_page_ratio:
            continue

        location_counts = dict(locations[normalized_text])
        edge_count = sum(
            count
            for location, count in location_counts.items()
            if location in {"top", "bottom", "left", "right"}
        )
        occurrence_count = sum(location_counts.values())
        edge_ratio = edge_count / max(occurrence_count, 1)

        reasons: list[str] = []
        if edge_ratio >= 0.6:
            reasons.append("repeats_near_page_edge")
        if page_ratio >= 0.1:
            reasons.append("high_page_recurrence")
        if len(normalized_text.split()) <= 8:
            reasons.append("short_repeated_phrase")

        candidates.append(
            RepeatedBlockCandidate(
                normalized_text=normalized_text,
                sample_text=samples[normalized_text],
                page_count=page_count,
                page_ratio=round(page_ratio, 6),
                locations=location_counts,
                sample_pages=sorted(pages)[:20],
                reasons=reasons,
            )
        )

    return sorted(
        candidates,
        key=lambda candidate: (-candidate.page_count, candidate.normalized_text),
    )


def build_page_audit(
    blocks: list[TextBlock],
    *,
    selected_pages: list[int],
    candidates: list[RepeatedBlockCandidate],
) -> dict[str, list[dict[str, Any]]]:
    candidate_map = {candidate.normalized_text: candidate for candidate in candidates}
    output: dict[str, list[dict[str, Any]]] = {}

    for page_number in selected_pages:
        page_output: list[dict[str, Any]] = []

        for block in blocks:
            if block.page_number != page_number:
                continue

            candidate = candidate_map.get(block.normalized_text)
            row = asdict(block)
            row["repeat_page_count"] = candidate.page_count if candidate else 0
            row["repeat_page_ratio"] = candidate.page_ratio if candidate else 0.0
            row["candidate_reasons"] = candidate.reasons if candidate else []
            page_output.append(row)

        output[str(page_number)] = page_output

    return output


def audit_pdf_layout(
    pdf_path: Path,
    *,
    selected_pages: list[int],
    max_pages: int | None = None,
    minimum_pages: int = 5,
    minimum_page_ratio: float = 0.02,
) -> dict[str, Any]:
    blocks, total_pages = extract_text_blocks(pdf_path, max_pages=max_pages)
    analyzed_pages = min(total_pages, max_pages) if max_pages else total_pages

    candidates = find_repeated_candidates(
        blocks,
        total_pages=analyzed_pages,
        minimum_pages=minimum_pages,
        minimum_page_ratio=minimum_page_ratio,
    )

    return {
        "pdf_path": str(pdf_path),
        "total_pages": total_pages,
        "analyzed_pages": analyzed_pages,
        "block_count": len(blocks),
        "candidate_count": len(candidates),
        "repeated_candidates": [asdict(candidate) for candidate in candidates],
        "selected_pages": build_page_audit(
            blocks,
            selected_pages=selected_pages,
            candidates=candidates,
        ),
    }
