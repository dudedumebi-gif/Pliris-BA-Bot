from __future__ import annotations

import pytest

from pliris.generation.citation_validator import CitationValidator
from pliris.generation.context_assembler import ContextAssembler
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedDraft,
    GroundedResponseValidationError,
    ResponseUsage,
)
from pliris.retrieval.models import RetrievedChunk


def context_with_sources():
    chunks = [
        RetrievedChunk(
            rank=1,
            chunk_id="chunk-1",
            text="Requirements traceability identifies lineage.",
            title="BABOK Guide",
            source="babok-v3",
            page_start=87,
            page_end=91,
            score=0.038,
            document_id="doc-1",
            metadata={"manifest_document_id": "babok-v3"},
        ),
        RetrievedChunk(
            rank=2,
            chunk_id="chunk-2",
            text="Traceability supports impact analysis.",
            title="BABOK Guide",
            source="babok-v3",
            page_start=90,
            page_end=93,
            score=0.037,
            document_id="doc-1",
            metadata={"manifest_document_id": "babok-v3"},
        ),
    ]
    return ContextAssembler().assemble(chunks)


def validate(draft: GroundedDraft):
    return CitationValidator().validate(
        draft,
        context_with_sources(),
        model="gpt-5-mini",
        response_id="resp-1",
        usage=ResponseUsage(
            input_tokens=100,
            output_tokens=40,
            total_tokens=140,
        ),
    )


def test_validator_maps_valid_inline_citations() -> None:
    answer = validate(
        GroundedDraft(
            answer=(
                "Requirements traceability records requirement "
                "lineage [S1] and supports impact analysis [S2]."
            ),
            citation_ids=("S1", "S2"),
            insufficient_evidence=False,
        )
    )

    assert answer.citation_ids == ("S1", "S2")
    assert [item.chunk_id for item in answer.citations] == [
        "chunk-1",
        "chunk-2",
    ]
    assert answer.usage.total_tokens == 140
    assert answer.metadata["available_source_count"] == 2
    assert answer.metadata["declared_citation_ids"] == (
        "S1",
        "S2",
    )
    assert answer.metadata["citation_ids_normalized"] is False


def test_validator_rejects_unknown_citation() -> None:
    with pytest.raises(
        GroundedResponseValidationError,
        match="Unknown citation identifiers: S3",
    ):
        validate(
            GroundedDraft(
                answer="Unsupported claim [S3].",
                citation_ids=("S3",),
                insufficient_evidence=False,
            )
        )


def test_validator_normalizes_declared_inline_mismatch() -> None:
    answer = validate(
        GroundedDraft(
            answer="Supported claim [S1].",
            citation_ids=("S2",),
            insufficient_evidence=False,
        )
    )

    assert answer.citation_ids == ("S1",)
    assert answer.metadata["declared_citation_ids"] == ("S2",)
    assert answer.metadata["citation_ids_normalized"] is True


def test_validator_rejects_malformed_citation_token() -> None:
    with pytest.raises(
        GroundedResponseValidationError,
        match="Malformed citation token",
    ):
        validate(
            GroundedDraft(
                answer="Supported claim [S1, S2].",
                citation_ids=("S1", "S2"),
                insufficient_evidence=False,
            )
        )


def test_validator_accepts_approved_insufficient_response() -> None:
    answer = validate(
        GroundedDraft(
            answer=INSUFFICIENT_EVIDENCE_MESSAGE,
            citation_ids=(),
            insufficient_evidence=True,
        )
    )

    assert answer.insufficient_evidence is True
    assert answer.citations == ()
    assert answer.citation_ids == ()


def test_validator_rejects_insufficient_response_with_citations() -> None:
    with pytest.raises(
        GroundedResponseValidationError,
        match="cannot cite sources",
    ):
        validate(
            GroundedDraft(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                citation_ids=("S1",),
                insufficient_evidence=True,
            )
        )


def test_validator_normalizes_declared_ids_to_inline_order() -> None:
    answer = validate(
        GroundedDraft(
            answer=(
                "Traceability supports impact analysis [S2] and records requirement lineage [S1]."
            ),
            citation_ids=("S1", "S2"),
            insufficient_evidence=False,
        )
    )

    assert answer.citation_ids == ("S2", "S1")
    assert [item.chunk_id for item in answer.citations] == [
        "chunk-2",
        "chunk-1",
    ]
