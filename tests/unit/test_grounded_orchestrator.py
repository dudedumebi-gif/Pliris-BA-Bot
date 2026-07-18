from __future__ import annotations

from typing import Any

import pytest

from pliris.agents.grounded_orchestrator import (
    GroundedResponseOrchestrator,
)
from pliris.database.repositories.grounded_persistence import (
    PersistenceOutcome,
)
from pliris.generation.context_assembler import (
    AssembledContext,
    ContextAssembler,
)
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedAnswer,
    ResponseUsage,
)
from pliris.retrieval.models import RetrievedChunk


def make_chunk(
    rank: int,
    *,
    chunk_id: str | None = None,
    text: str | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        chunk_id=chunk_id or f"chunk-{rank}",
        text=text or f"Evidence from chunk {rank}.",
        title="BABOK Guide",
        source="babok-v3",
        page_start=80 + rank,
        page_end=82 + rank,
        score=0.04 - rank / 1000,
        document_id="doc-1",
        metadata={
            "manifest_document_id": "babok-v3",
            "semantic_rank": rank,
            "keyword_rank": rank + 1,
        },
    )


class FakeRetriever:
    def __init__(
        self,
        chunks: list[RetrievedChunk],
    ) -> None:
        self.chunks = chunks
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: str,
        *,
        top_k: int,
        document_id: str | None,
    ) -> list[RetrievedChunk]:
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "document_id": document_id,
            }
        )
        return self.chunks[:top_k]


class FakeGenerator:
    def __init__(
        self,
        *,
        insufficient: bool = False,
        missing_citation: bool = False,
    ) -> None:
        self.insufficient = insufficient
        self.missing_citation = missing_citation
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        *,
        question: str,
        context: AssembledContext,
    ) -> GroundedAnswer:
        self.calls.append(
            {
                "question": question,
                "context": context,
            }
        )

        if self.insufficient:
            return GroundedAnswer(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                citation_ids=(),
                citations=(),
                insufficient_evidence=True,
                model="gpt-5-mini",
                response_id=None,
                usage=ResponseUsage(),
                metadata={},
            )

        citation_id = "S9" if self.missing_citation else context.sources[0].citation_id
        citations = () if self.missing_citation else (context.sources[0],)
        return GroundedAnswer(
            answer=f"Grounded answer [{citation_id}].",
            citation_ids=(citation_id,),
            citations=citations,
            insufficient_evidence=False,
            model="gpt-5-mini-2025-08-07",
            response_id="resp-1",
            usage=ResponseUsage(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            ),
            metadata={},
        )


class FakePersistence:
    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.error = error
        self.exchanges: list[Any] = []

    async def persist_exchange(self, exchange: Any) -> Any:
        self.exchanges.append(exchange)
        if self.error is not None:
            raise self.error
        return PersistenceOutcome(
            client_session_id="persisted-session",
            database_conversation_id="db-conversation",
            user_message_id="user-message",
            assistant_message_id="assistant-message",
            retrieval_query_id="retrieval-query",
            monitoring_event_id="monitoring-event",
            retrieval_result_count=len(exchange.chunks),
        )


@pytest.mark.asyncio
async def test_pipeline_connects_production_components() -> None:
    retriever = FakeRetriever([make_chunk(1), make_chunk(2)])
    generator = FakeGenerator()
    orchestrator = GroundedResponseOrchestrator(
        retriever=retriever,
        context_assembler=ContextAssembler(max_chunks=5),
        generator=generator,
        top_k=5,
    )

    result = await orchestrator.process_query(
        message="  What is requirements traceability?  ",
        conversation_id="conv-1",
        user_id="user-1",
        document_id="babok-v3",
    )

    assert retriever.calls == [
        {
            "query": "What is requirements traceability?",
            "top_k": 5,
            "document_id": "babok-v3",
        }
    ]
    assert generator.calls[0]["question"] == ("What is requirements traceability?")
    assert "[S1]" in generator.calls[0]["context"].text

    assert result.response == "Grounded answer [S1]."
    assert result.conversation_id == "conv-1"
    assert result.confidence == 1.0
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk-1"
    assert result.citations[0].page == 81
    assert result.usage["total_tokens"] == 120
    assert result.metadata["user_id"] == "user-1"
    assert result.metadata["retrieved_count"] == 2
    assert result.metadata["persistence"] == {"status": "disabled"}


@pytest.mark.asyncio
async def test_pipeline_persists_exchange_and_returns_session() -> None:
    persistence = FakePersistence()
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([make_chunk(1)]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(),
        persistence_repository=persistence,
    )

    result = await orchestrator.process_query(
        message="What is traceability?",
        conversation_id=None,
        user_id="user-1",
        document_id="babok-v3",
        scope_status="in_scope",
        scope_confidence=0.8,
        scope_category="business_analysis",
    )

    assert result.conversation_id == "persisted-session"
    assert result.metadata["persistence"]["status"] == ("completed")
    assert result.metadata["persistence"]["database_conversation_id"] == "db-conversation"
    assert result.metadata["persistence"]["retrieval_result_count"] == 1

    exchange = persistence.exchanges[0]
    assert exchange.user_id == "user-1"
    assert exchange.scope_confidence == 0.8
    assert exchange.scope_category == "business_analysis"
    assert exchange.requested_match_count == 5
    assert exchange.selected_chunk_ids == frozenset({"chunk-1"})
    assert exchange.citations[0]["citation_id"] == "S1"
    assert exchange.metadata["retrieved_count"] == 1


@pytest.mark.asyncio
async def test_pipeline_returns_answer_when_persistence_fails() -> None:
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([make_chunk(1)]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(),
        persistence_repository=FakePersistence(error=RuntimeError("database unavailable")),
    )

    result = await orchestrator.process_query(
        message="What is traceability?",
        conversation_id="conv-original",
    )

    assert result.response == "Grounded answer [S1]."
    assert result.conversation_id == "conv-original"
    assert result.metadata["persistence"]["status"] == "failed"
    assert result.metadata["persistence"]["error_type"] == ("RuntimeError")
    assert result.metadata["persistence"]["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_pipeline_returns_zero_confidence_when_insufficient() -> None:
    persistence = FakePersistence()
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(insufficient=True),
        persistence_repository=persistence,
    )

    result = await orchestrator.process_query(
        message="Question without evidence",
    )

    assert result.response == INSUFFICIENT_EVIDENCE_MESSAGE
    assert result.insufficient_evidence is True
    assert result.citations == ()
    assert result.confidence == 0.0
    assert result.metadata["retrieved_count"] == 0
    assert persistence.exchanges[0].chunks == ()
    assert persistence.exchanges[0].citations == ()


@pytest.mark.asyncio
async def test_pipeline_fails_closed_on_missing_context_citation() -> None:
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([make_chunk(1)]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(missing_citation=True),
    )

    with pytest.raises(
        RuntimeError,
        match="citation absent from assembled context",
    ):
        await orchestrator.process_query(
            message="What is traceability?",
        )


@pytest.mark.asyncio
async def test_pipeline_citation_preserves_api_ready_excerpt() -> None:
    chunk = make_chunk(
        1,
        text="Requirements traceability identifies lineage.",
    )
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([chunk]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(),
    )

    result = await orchestrator.process_query(
        message="What is traceability?",
    )
    citation = result.to_dict()["citations"][0]

    assert citation["citation_id"] == "S1"
    assert citation["text"] == ("Requirements traceability identifies lineage.")
    assert citation["source"] == "babok-v3"
    assert citation["metadata"]["semantic_rank"] == 1


@pytest.mark.asyncio
async def test_pipeline_validates_inputs() -> None:
    with pytest.raises(
        ValueError,
        match="top_k must be positive",
    ):
        GroundedResponseOrchestrator(
            retriever=FakeRetriever([]),
            generator=FakeGenerator(),
            top_k=0,
        )

    with pytest.raises(
        ValueError,
        match="top_k cannot exceed 20",
    ):
        GroundedResponseOrchestrator(
            retriever=FakeRetriever([]),
            generator=FakeGenerator(),
            top_k=21,
        )

    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([]),
        generator=FakeGenerator(),
    )
    with pytest.raises(
        ValueError,
        match="message must not be blank",
    ):
        await orchestrator.process_query(message="   ")


@pytest.mark.asyncio
async def test_pipeline_truncates_public_citation_excerpt() -> None:
    long_text = " ".join(f"requirement-{index}" for index in range(100))
    chunk = make_chunk(1, text=long_text)
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([chunk]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(),
    )

    result = await orchestrator.process_query(
        message="What is traceability?",
    )

    citation_text = result.citations[0].text

    assert len(citation_text) <= 600
    assert citation_text.endswith("…")
    assert "\n" not in citation_text
    assert citation_text != long_text


@pytest.mark.asyncio
async def test_pipeline_preserves_short_citation_excerpt() -> None:
    chunk = make_chunk(
        1,
        text="  Requirements\ntraceability records lineage.  ",
    )
    orchestrator = GroundedResponseOrchestrator(
        retriever=FakeRetriever([chunk]),
        context_assembler=ContextAssembler(),
        generator=FakeGenerator(),
    )

    result = await orchestrator.process_query(
        message="What is traceability?",
    )

    assert result.citations[0].text == ("Requirements traceability records lineage.")
