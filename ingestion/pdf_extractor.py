from __future__ import annotations

from pathlib import Path

import fitz

from ingestion.models import ExtractedDocument, ExtractedPage


def extract_pdf(
    path: Path,
    *,
    max_pages: int | None = None,
    low_text_threshold: int = 40,
) -> ExtractedDocument:
    """Extract sorted plain text page by page while preserving page numbers."""
    if not path.exists():
        raise FileNotFoundError(path)

    pages: list[ExtractedPage] = []
    document_warnings: list[str] = []

    with fitz.open(path) as pdf:
        total_pages = pdf.page_count
        pages_to_read = min(total_pages, max_pages) if max_pages else total_pages

        for page_index in range(pages_to_read):
            page = pdf.load_page(page_index)
            text = page.get_text("text", sort=True).strip()
            warnings: list[str] = []

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

    return ExtractedDocument(
        path=path,
        page_count=total_pages,
        pages=pages,
        pdf_metadata=metadata,
        warnings=document_warnings,
    )
