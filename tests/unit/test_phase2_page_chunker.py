from ingestion.models import ExtractedPage
from ingestion.page_chunker import chunk_pages


def test_chunk_pages_preserves_page_metadata() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="STAKEHOLDER ANALYSIS\n\n" + ("Stakeholder needs and influence. " * 60),
            character_count=1000,
        ),
        ExtractedPage(
            page_number=2,
            text="REQUIREMENTS\n\n" + ("Requirements must be traceable and testable. " * 60),
            character_count=1000,
        ),
    ]

    chunks = chunk_pages(
        pages,
        document_id="sample",
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) > 1
    assert chunks[0].page_start >= 1
    assert chunks[-1].page_end <= 2
    assert all(chunk.content_hash for chunk in chunks)
    assert all(chunk.token_count <= 100 for chunk in chunks)
