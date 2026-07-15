"""Chunk documents for retrieval."""

import logging

from pliris.config.settings import settings

logger = logging.getLogger(__name__)


def chunk_document(
    text: str, 
    metadata: dict, 
    chunk_size: int | None = None, 
    chunk_overlap: int | None = None
) -> list[dict]:
    """
    Split document text into chunks.

    Args:
        text: Document text
        metadata: Document metadata
        chunk_size: Size of each chunk (defaults to settings)
        chunk_overlap: Overlap between chunks (defaults to settings)

    Returns:
        List of chunk dictionaries
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    chunks = []

    # Split by paragraphs first
    paragraphs = text.split("\n\n")

    current_chunk = ""
    current_size = 0
    chunk_index = 0

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        paragraph_size = len(paragraph)

        # If adding this paragraph would exceed chunk size
        if current_size + paragraph_size > chunk_size and current_chunk:
            # Save current chunk
            chunks.append(
                {
                    "text": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "metadata": {
                        **metadata,
                        "chunk_size": len(current_chunk),
                        "chunk_index": chunk_index,
                    },
                }
            )

            # Start new chunk with overlap
            current_chunk = _get_overlap_text(current_chunk, chunk_overlap)
            current_size = len(current_chunk)
            chunk_index += 1

        # Add paragraph to current chunk
        current_chunk += "\n\n" + paragraph if current_chunk else paragraph
        current_size += paragraph_size + 2

    # Add final chunk if not empty
    if current_chunk.strip():
        chunks.append(
            {
                "text": current_chunk.strip(),
                "chunk_index": chunk_index,
                "metadata": {
                    **metadata,
                    "chunk_size": len(current_chunk),
                    "chunk_index": chunk_index,
                },
            }
        )

    logger.info(f"Created {len(chunks)} chunks from document")

    return chunks


def _get_overlap_text(text: str, overlap_size: int) -> str:
    """
    Get the last N characters of text for overlap.

    Args:
        text: Current chunk text
        overlap_size: Desired overlap size

    Returns:
        Overlap text
    """
    if overlap_size <= 0:
        return ""

    # Get last overlap_size characters
    overlap = text[-overlap_size:]

    # Try to break at a sentence boundary
    sentences = overlap.split(".")
    if len(sentences) > 1:
        # Return from the start of the last complete sentence
        return ".".join(sentences[:-1]) + "."

    return overlap


def merge_chunks(chunks: list[dict], separator: str = "\n\n") -> str:
    """
    Merge chunks back into a single document.

    Args:
        chunks: List of chunk dictionaries
        separator: Separator between chunks

    Returns:
        Merged text
    """
    # Sort by chunk index
    sorted_chunks = sorted(chunks, key=lambda x: x.get("chunk_index", 0))

    # Extract text and join
    texts = [chunk["text"] for chunk in sorted_chunks]

    return separator.join(texts)
