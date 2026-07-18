from __future__ import annotations

from pliris.generation.context_assembler import (
    NO_CONTEXT_MESSAGE,
    ContextAssembler,
)
from pliris.retrieval.models import RetrievedChunk


def chunk(
    rank: int,
    *,
    chunk_id: str | None = None,
    text: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        chunk_id=chunk_id or f"chunk-{rank}",
        text=text or f"Content for chunk {rank}.",
        title="BABOK Guide",
        source="babok-v3/guide.pdf",
        page_start=page_start if page_start is not None else rank,
        page_end=page_end if page_end is not None else rank + 1,
        score=1.0 / rank,
        document_id="document-id",
        metadata={"manifest_id": "babok-v3"},
    )


def test_assemble_creates_stable_citation_labels() -> None:
    assembled = ContextAssembler().assemble(
        [
            chunk(2, page_start=20, page_end=22),
            chunk(1, page_start=12, page_end=14),
        ]
    )

    assert [source.citation_id for source in assembled.sources] == [
        "S1",
        "S2",
    ]
    assert [source.rank for source in assembled.sources] == [1, 2]
    assert assembled.sources[0].page_label == "12-14"
    assert assembled.text.startswith("[S1]\nTitle: BABOK Guide")
    assert "\n\n[S2]\n" in assembled.text
    assert assembled.omitted_count == 0
    assert assembled.truncated is False


def test_assemble_deduplicates_and_ignores_empty_chunks() -> None:
    assembled = ContextAssembler(max_chunks=5).assemble(
        [
            chunk(1, chunk_id="same", text="Primary content."),
            chunk(2, chunk_id="same", text="Duplicate content."),
            chunk(3, text="   "),
            chunk(4, text="Additional content."),
        ]
    )

    assert len(assembled.sources) == 2
    assert [source.rank for source in assembled.sources] == [1, 4]
    assert "Duplicate content." not in assembled.text


def test_assemble_limits_context_to_top_five() -> None:
    assembled = ContextAssembler(max_chunks=5).assemble([chunk(rank) for rank in range(1, 8)])

    assert len(assembled.sources) == 5
    assert assembled.omitted_count == 2
    assert assembled.truncated is True
    assert "[S5]" in assembled.text
    assert "[S6]" not in assembled.text


def test_assemble_respects_character_budget() -> None:
    assembled = ContextAssembler(
        max_chunks=5,
        max_characters=260,
        minimum_content_characters=40,
    ).assemble(
        [
            chunk(
                1,
                text=(
                    "Business analysis enables change by defining needs "
                    "and recommending solutions that deliver value. " * 8
                ),
            ),
            chunk(2),
        ]
    )

    assert assembled.character_count <= 260
    assert assembled.text.endswith("...")
    assert len(assembled.sources) == 1
    assert assembled.omitted_count == 1
    assert assembled.truncated is True


def test_assemble_empty_context_returns_sentinel() -> None:
    assembled = ContextAssembler().assemble([])

    assert assembled.text == NO_CONTEXT_MESSAGE
    assert assembled.sources == ()
    assert assembled.omitted_count == 0
    assert assembled.character_count == len(NO_CONTEXT_MESSAGE)
    assert assembled.truncated is False


def test_context_source_is_citation_ready() -> None:
    assembled = ContextAssembler().assemble([chunk(1, page_start=44, page_end=44)])
    source = assembled.sources[0].to_dict()

    assert source["citation_id"] == "S1"
    assert source["chunk_id"] == "chunk-1"
    assert source["page_label"] == "44"
    assert source["document_id"] == "document-id"
    assert source["metadata"]["manifest_id"] == "babok-v3"
