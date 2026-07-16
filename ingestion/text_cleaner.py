from __future__ import annotations

import re
from collections import Counter

from ingestion.models import ExtractedPage

_WHITESPACE_RE = re.compile(r"[ \t]+")
_MANY_BLANK_LINES_RE = re.compile(r"\n{3,}")
_HYPHENATED_LINE_BREAK_RE = re.compile(r"(?<=\w)-\n(?=[a-z])")
_SOFT_LINE_BREAK_RE = re.compile(r"(?<![.!?:;\n])\n(?=[a-z])")


def normalize_page_text(text: str) -> str:
    """Normalize extraction artifacts without flattening meaningful paragraphs."""
    text = text.replace("\u00a0", " ")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "--")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHENATED_LINE_BREAK_RE.sub("", text)
    text = _SOFT_LINE_BREAK_RE.sub(" ", text)

    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    normalized = "\n".join(lines)
    normalized = _MANY_BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized.strip()


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


def _last_non_empty_line(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return None


def _repeated_margin_lines(
    pages: list[ExtractedPage],
    *,
    minimum_occurrences: int = 3,
    ratio: float = 0.6,
) -> set[str]:
    if not pages:
        return set()

    candidates: list[str] = []
    for page in pages:
        first = _first_non_empty_line(page.text)
        last = _last_non_empty_line(page.text)
        if first and len(first) <= 160:
            candidates.append(first)
        if last and len(last) <= 160:
            candidates.append(last)

    threshold = max(minimum_occurrences, int(len(pages) * ratio))
    return {line for line, count in Counter(candidates).items() if count >= threshold}


def clean_pages(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    """Normalize pages and remove headers or footers repeated across the document."""
    normalized_pages = [
        ExtractedPage(
            page_number=page.page_number,
            text=normalize_page_text(page.text),
            character_count=page.character_count,
            warnings=list(page.warnings),
        )
        for page in pages
    ]

    repeated_lines = _repeated_margin_lines(normalized_pages)
    cleaned_pages: list[ExtractedPage] = []

    for page in normalized_pages:
        lines = [line for line in page.text.splitlines() if line.strip() not in repeated_lines]
        cleaned_text = "\n".join(lines).strip()
        warnings = list(page.warnings)

        if repeated_lines and cleaned_text != page.text:
            warnings.append("repeated_header_or_footer_removed")

        cleaned_pages.append(
            ExtractedPage(
                page_number=page.page_number,
                text=cleaned_text,
                character_count=len(cleaned_text),
                warnings=warnings,
            )
        )

    return cleaned_pages
