from __future__ import annotations

from pathlib import Path

import fitz

from ingestion.layout_filter import (
    LayoutFilterStats,
    blocks_to_text,
    build_layout_filter_policy,
    filter_blocks,
    page_text_blocks,
)
from ingestion.models import ExtractedDocument, ExtractedPage


def extract_pdf(
    path: Path,
    *,
    max_pages: int | None = None,
    low_text_threshold: int = 40,
    remove_layout_artifacts: bool = True,
) -> ExtractedDocument:
    """
    Extract page-aware text and conservatively remove proven layout artifacts.

    The learned policy removes only near-universal repeated edge phrases.
    Printed page numbers are removed with strict bottom-centre geometry.
    """
    if not path.exists():
        raise FileNotFoundError(path)

    policy = (
        build_layout_filter_policy(path, max_pages=max_pages) if remove_layout_artifacts else None
    )

    pages: list[ExtractedPage] = []
    document_warnings: list[str] = []
    total_filter_stats = LayoutFilterStats()

    with fitz.open(path) as pdf:
        total_pages = pdf.page_count
        pages_to_read = min(total_pages, max_pages) if max_pages else total_pages

        for page_index in range(pages_to_read):
            page = pdf.load_page(page_index)
            warnings: list[str] = []

            if policy is not None:
                blocks = page_text_blocks(
                    page,
                    page_number=page_index + 1,
                )
                kept, page_stats, _removed = filter_blocks(blocks, policy)
                total_filter_stats.add(page_stats)
                text = blocks_to_text(kept)
            else:
                text = page.get_text("text", sort=True).strip()

            if not text:
                warnings.append("empty_page")
            elif len(text) < low_text_threshold:
                warnings.append("low_text_page")

            pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text=text,
                    character_count=len(text),
                    warnings=warnings,
                )
            )

        if max_pages and max_pages < total_pages:
            document_warnings.append(
                f"Extraction limited to the first {pages_to_read} of {total_pages} pages."
            )

        metadata = {
            key: value for key, value in (pdf.metadata or {}).items() if value not in (None, "")
        }

    if policy is not None:
        document_warnings.append(
            "Layout filter learned "
            f"{len(policy.repeated_artifact_texts)} repeated artifact pattern(s)."
        )
        document_warnings.append(
            "Layout filter removed "
            f"{total_filter_stats.removed_repeated_artifacts} recurring edge "
            "block(s) and "
            f"{total_filter_stats.removed_page_numbers} printed page number(s)."
        )

    return ExtractedDocument(
        path=path,
        page_count=total_pages,
        pages=pages,
        pdf_metadata=metadata,
        warnings=document_warnings,
    )
