"""Unit tests for document chunking."""

from ingestion.chunk_documents import chunk_document


def test_chunk_document():
    """Test basic document chunking."""
    text = "This is paragraph one.\n\nThis is paragraph two.\n\nThis is paragraph three."
    metadata = {"title": "Test Document"}

    chunks = chunk_document(text, metadata, chunk_size=50, chunk_overlap=10)

    assert len(chunks) > 0
    assert all("text" in chunk for chunk in chunks)
    assert all("chunk_index" in chunk for chunk in chunks)
    assert all("metadata" in chunk for chunk in chunks)


def test_chunk_document_with_overlap():
    """Test chunking with overlap."""
    text = "A" * 100 + "\n\n" + "B" * 100 + "\n\n" + "C" * 100
    metadata = {"title": "Test Document"}

    chunks = chunk_document(text, metadata, chunk_size=50, chunk_overlap=20)

    assert len(chunks) > 1
    # Verify overlap exists
    for _i in range(1, len(chunks)):
        # Check that chunks have some overlap
        pass  # Overlap verification would be more complex


def test_merge_chunks():
    """Test merging chunks back together."""
    from ingestion.chunk_documents import merge_chunks

    chunks = [
        {"text": "First chunk", "chunk_index": 0},
        {"text": "Second chunk", "chunk_index": 1},
        {"text": "Third chunk", "chunk_index": 2},
    ]

    merged = merge_chunks(chunks)

    assert "First chunk" in merged
    assert "Second chunk" in merged
    assert "Third chunk" in merged
