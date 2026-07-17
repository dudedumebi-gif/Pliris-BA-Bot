from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from ingestion.layout_audit import (
    TextBlock,
    classify_location,
    extract_text_blocks,
    normalize_block_text,
)

_NUMERIC_ONLY_RE = re.compile(r"^\s*\d+\s*$")


@dataclass(frozen=True, slots=True)
class LayoutFilterPolicy:
    """Conservative document-level rules learned from positioned text blocks."""

    total_pages: int
    analyzed_pages: int
    repeated_artifact_texts: frozenset[str]
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(slots=True)
class LayoutFilterStats:
    kept_blocks: int = 0
    removed_repeated_artifacts: int = 0
    removed_page_numbers: int = 0

    @property
    def removed_blocks(self) -> int:
        return self.removed_repeated_artifacts + self.removed_page_numbers

    def add(self, other: LayoutFilterStats) -> None:
        self.kept_blocks += other.kept_blocks
        self.removed_repeated_artifacts += other.removed_repeated_artifacts
        self.removed_page_numbers += other.removed_page_numbers


def block_from_tuple(
    item: tuple[Any, ...],
    *,
    page_number: int,
    page_width: float,
    page_height: float,
    fallback_block_number: int,
) -> TextBlock | None:
    if len(item) < 5:
        return None

    x0, y0, x1, y1 = map(float, item[:4])
    text = str(item[4]).strip()
    if not text:
        return None

    normalized_text = normalize_block_text(text)
    if not normalized_text:
        return None

    block_number = int(item[5]) if len(item) > 5 else fallback_block_number

    return TextBlock(
        page_number=page_number,
        block_number=block_number,
        text=text,
        normalized_text=normalized_text,
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


def page_text_blocks(
    page: fitz.Page,
    *,
    page_number: int,
) -> list[TextBlock]:
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    blocks: list[TextBlock] = []

    for fallback_number, item in enumerate(page.get_text("blocks", sort=True)):
        block = block_from_tuple(
            item,
            page_number=page_number,
            page_width=page_width,
            page_height=page_height,
            fallback_block_number=fallback_number,
        )
        if block is not None:
            blocks.append(block)

    return blocks


def build_layout_filter_policy(
    pdf_path: Path,
    *,
    max_pages: int | None = None,
    minimum_pages: int = 20,
    minimum_page_ratio: float = 0.8,
    minimum_edge_ratio: float = 0.8,
    minimum_text_length: int = 12,
) -> LayoutFilterPolicy:
    """
    Learn only near-universal repeated edge artifacts.

    Numeric-only blocks are excluded because printed page numbers are handled
    with geometry instead of recurrence.
    """
    blocks, total_pages = extract_text_blocks(
        pdf_path,
        max_pages=max_pages,
    )
    analyzed_pages = min(total_pages, max_pages) if max_pages else total_pages

    pages_by_text: dict[str, set[int]] = defaultdict(set)
    locations: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, str] = {}

    for block in blocks:
        pages_by_text[block.normalized_text].add(block.page_number)
        locations[block.normalized_text][block.location] += 1
        samples.setdefault(block.normalized_text, block.text)

    repeated_artifacts: set[str] = set()
    evidence: dict[str, dict[str, Any]] = {}

    for normalized_text, pages in pages_by_text.items():
        page_count = len(pages)
        page_ratio = page_count / max(analyzed_pages, 1)
        location_counts = locations[normalized_text]
        occurrence_count = sum(location_counts.values())
        edge_count = sum(
            count
            for location, count in location_counts.items()
            if location in {"top", "bottom", "left", "right"}
        )
        edge_ratio = edge_count / max(occurrence_count, 1)
        sample_text = samples[normalized_text]

        if _NUMERIC_ONLY_RE.fullmatch(sample_text):
            continue

        if (
            page_count >= minimum_pages
            and page_ratio >= minimum_page_ratio
            and edge_ratio >= minimum_edge_ratio
            and len(normalized_text) >= minimum_text_length
        ):
            repeated_artifacts.add(normalized_text)
            evidence[normalized_text] = {
                "sample_text": sample_text,
                "page_count": page_count,
                "page_ratio": round(page_ratio, 6),
                "edge_ratio": round(edge_ratio, 6),
                "locations": dict(location_counts),
            }

    return LayoutFilterPolicy(
        total_pages=total_pages,
        analyzed_pages=analyzed_pages,
        repeated_artifact_texts=frozenset(repeated_artifacts),
        evidence=evidence,
    )


def is_printed_page_number(block: TextBlock) -> bool:
    if not _NUMERIC_ONLY_RE.fullmatch(block.text):
        return False

    width = block.x1 - block.x0
    height = block.y1 - block.y0
    center_x_ratio = ((block.x0 + block.x1) / 2) / block.page_width
    y0_ratio = block.y0 / block.page_height

    return (
        block.location == "bottom"
        and y0_ratio >= 0.93
        and 0.38 <= center_x_ratio <= 0.62
        and width <= 60
        and height <= 30
    )


def removal_reason(
    block: TextBlock,
    policy: LayoutFilterPolicy,
) -> str | None:
    if block.normalized_text in policy.repeated_artifact_texts:
        return "repeated_edge_artifact"

    if is_printed_page_number(block):
        return "printed_page_number"

    return None


def filter_blocks(
    blocks: Iterable[TextBlock],
    policy: LayoutFilterPolicy,
) -> tuple[list[TextBlock], LayoutFilterStats, list[dict[str, Any]]]:
    kept: list[TextBlock] = []
    stats = LayoutFilterStats()
    removed: list[dict[str, Any]] = []

    for block in blocks:
        reason = removal_reason(block, policy)
        if reason is None:
            kept.append(block)
            stats.kept_blocks += 1
            continue

        if reason == "repeated_edge_artifact":
            stats.removed_repeated_artifacts += 1
        elif reason == "printed_page_number":
            stats.removed_page_numbers += 1

        removed.append(
            {
                "page_number": block.page_number,
                "block_number": block.block_number,
                "reason": reason,
                "location": block.location,
                "text": block.text,
                "bbox": [block.x0, block.y0, block.x1, block.y1],
            }
        )

    return kept, stats, removed


def blocks_to_text(blocks: Iterable[TextBlock]) -> str:
    return "\n\n".join(block.text.strip() for block in blocks if block.text.strip()).strip()
