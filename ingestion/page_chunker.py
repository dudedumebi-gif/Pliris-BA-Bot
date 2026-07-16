from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import tiktoken

from ingestion.models import DocumentChunk, ExtractedPage
from pliris.config.settings import get_settings

_HEADING_RE = re.compile(r"^[A-Z][A-Za-z0-9,&()/:\- ]{2,100}$")


@dataclass(slots=True)
class TextUnit:
    page_number: int
    text: str
    heading: str | None


def _encoding() -> tiktoken.Encoding:
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return tiktoken.encoding_for_model("gpt-4o-mini")


def _is_heading(line: str) -> bool:
    cleaned = line.strip()
    if not cleaned or len(cleaned) > 100:
        return False
    if cleaned.endswith((".", ",", ";")):
        return False
    if cleaned.isupper() and 2 <= len(cleaned.split()) <= 12:
        return True
    return bool(_HEADING_RE.fullmatch(cleaned)) and len(cleaned.split()) <= 12


def _page_units(pages: list[ExtractedPage]) -> list[TextUnit]:
    units: list[TextUnit] = []
    active_heading: str | None = None

    for page in pages:
        paragraphs = [
            paragraph.strip() for paragraph in re.split(r"\n\s*\n", page.text) if paragraph.strip()
        ]

        for paragraph in paragraphs:
            lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
            if not lines:
                continue

            if len(lines) == 1 and _is_heading(lines[0]):
                active_heading = lines[0]
                continue

            if _is_heading(lines[0]) and len(lines) > 1:
                active_heading = lines[0]
                paragraph = "\n".join(lines[1:]).strip()

            if paragraph:
                units.append(
                    TextUnit(
                        page_number=page.page_number,
                        text=paragraph,
                        heading=active_heading,
                    )
                )

    return units


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    document_id: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[DocumentChunk]:
    """Create token-bounded, page-aware chunks with deterministic hashes."""
    settings = get_settings()
    size = chunk_size or settings.chunk_size_tokens
    overlap = settings.chunk_overlap_tokens if chunk_overlap is None else chunk_overlap

    if size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if overlap < 0 or overlap >= size:
        raise ValueError("chunk_overlap must be at least zero and smaller than chunk_size.")

    encoding = _encoding()
    units = _page_units(pages)
    token_stream: list[tuple[int, int, str | None]] = []

    for unit in units:
        for token in encoding.encode(unit.text):
            token_stream.append((token, unit.page_number, unit.heading))

    if not token_stream:
        return []

    chunks: list[DocumentChunk] = []
    step = size - overlap
    start = 0
    chunk_index = 0

    while start < len(token_stream):
        window = token_stream[start : start + size]
        token_ids = [item[0] for item in window]
        content = encoding.decode(token_ids).strip()

        if content:
            pages_in_chunk = [item[1] for item in window]
            headings = [item[2] for item in window if item[2] is not None]
            heading = headings[-1] if headings else None
            heading_path = [heading] if heading else []

            chunks.append(
                DocumentChunk(
                    chunk_index=chunk_index,
                    content=content,
                    page_start=min(pages_in_chunk),
                    page_end=max(pages_in_chunk),
                    chapter=None,
                    section=heading,
                    heading_path=heading_path,
                    token_count=len(token_ids),
                    content_hash=_hash_content(content),
                    metadata={"manifest_document_id": document_id},
                )
            )
            chunk_index += 1

        if start + size >= len(token_stream):
            break
        start += step

    return chunks
