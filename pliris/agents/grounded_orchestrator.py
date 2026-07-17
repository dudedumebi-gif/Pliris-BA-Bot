from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any

from pliris.generation.context_assembler import (
    AssembledContext,
    ContextAssembler,
)
from pliris.generation.grounded_generator import (
    GroundedResponseGenerator,
)
from pliris.generation.grounded_models import GroundedAnswer
from pliris.retrieval.hosted_hybrid import HostedHybridRetriever
from pliris.retrieval.models import RetrievedChunk


@dataclass(frozen=True, slots=True)
class PipelineCitation:
    """API-ready citation derived from one retrieved chunk."""

    citation_id: str
    chunk_id: str
    source: str
    title: str
    text: str
    page: int | None
    page_start: int | None
    page_end: int | None
    score: float
    rank: int
    document_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GroundedPipelineResult:
    """Result returned by the production grounded pipeline."""

    response: str
    citations: tuple[PipelineCitation, ...]
    insufficient_evidence: bool
    conversation_id: str | None
    model: str
    response_id: str | None
    usage: dict[str, int | None]
    metadata: dict[str, Any]

    @property
    def confidence(self) -> float:
        if self.insufficient_evidence:
            return 0.0
        if not self.citations:
            return 0.0
        return 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "response": self.response,
            "citations": [citation.to_dict() for citation in self.citations],
            "confidence": self.confidence,
            "insufficient_evidence": self.insufficient_evidence,
            "conversation_id": self.conversation_id,
            "model": self.model,
            "response_id": self.response_id,
            "usage": dict(self.usage),
            "metadata": dict(self.metadata),
        }


class GroundedResponseOrchestrator:
    """
    Connect hosted retrieval, deterministic context assembly, and grounded
    generation without persistence or API-route changes.
    """

    def __init__(
        self,
        *,
        retriever: Any | None = None,
        context_assembler: ContextAssembler | None = None,
        generator: Any | None = None,
        top_k: int = 5,
    ) -> None:
        if top_k < 1:
            raise ValueError("top_k must be positive.")
        if top_k > 20:
            raise ValueError("top_k cannot exceed 20.")

        self.retriever = retriever or HostedHybridRetriever()
        self.context_assembler = context_assembler or ContextAssembler(max_chunks=top_k)
        self.generator = generator or GroundedResponseGenerator()
        self.top_k = top_k

    async def process_query(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
        user_id: str = "system",
        document_id: str | None = None,
    ) -> GroundedPipelineResult:
        normalized_message = message.strip()
        if not normalized_message:
            raise ValueError("message must not be blank.")

        total_started = perf_counter()

        retrieval_started = perf_counter()
        chunks = await self.retriever.search(
            normalized_message,
            top_k=self.top_k,
            document_id=document_id,
        )
        retrieval_ms = self._elapsed_ms(retrieval_started)

        assembly_started = perf_counter()
        context = self.context_assembler.assemble(chunks)
        assembly_ms = self._elapsed_ms(assembly_started)

        generation_started = perf_counter()
        answer = await self.generator.generate(
            question=normalized_message,
            context=context,
        )
        generation_ms = self._elapsed_ms(generation_started)

        citations = self._build_citations(
            answer=answer,
            context=context,
            chunks=chunks,
        )

        return GroundedPipelineResult(
            response=answer.answer,
            citations=tuple(citations),
            insufficient_evidence=(answer.insufficient_evidence),
            conversation_id=conversation_id,
            model=answer.model,
            response_id=answer.response_id,
            usage=self._usage_dict(answer.usage),
            metadata={
                "user_id": user_id,
                "document_id": document_id,
                "retrieved_count": len(chunks),
                "context_source_count": len(context.sources),
                "context_character_count": (context.character_count),
                "context_truncated": context.truncated,
                "context_omitted_count": (context.omitted_count),
                "retrieval_ms": retrieval_ms,
                "assembly_ms": assembly_ms,
                "generation_ms": generation_ms,
                "total_ms": self._elapsed_ms(total_started),
                "confidence_basis": "validated_citation_contract",
                "generation": dict(answer.metadata),
            },
        )

    @staticmethod
    def _build_citations(
        *,
        answer: GroundedAnswer,
        context: AssembledContext,
        chunks: list[RetrievedChunk],
    ) -> list[PipelineCitation]:
        if answer.insufficient_evidence:
            return []

        chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        context_by_id = {source.citation_id: source for source in context.sources}

        citations: list[PipelineCitation] = []
        for citation_id in answer.citation_ids:
            source = context_by_id.get(citation_id)
            if source is None:
                raise RuntimeError(
                    "Grounded answer referenced a citation absent "
                    f"from assembled context: {citation_id}"
                )

            chunk = chunks_by_id.get(source.chunk_id)
            if chunk is None:
                raise RuntimeError(
                    "Assembled context referenced a chunk absent "
                    f"from retrieval results: {source.chunk_id}"
                )

            citations.append(
                PipelineCitation(
                    citation_id=citation_id,
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    title=chunk.title,
                    text=chunk.text,
                    page=chunk.page_start,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    score=chunk.score,
                    rank=chunk.rank,
                    document_id=chunk.document_id,
                    metadata=dict(chunk.metadata),
                )
            )

        return citations

    @staticmethod
    def _usage_dict(usage: Any) -> dict[str, int | None]:
        if isinstance(usage, dict):
            return dict(usage)
        to_dict = getattr(usage, "to_dict", None)
        if callable(to_dict):
            return dict(to_dict())
        return {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 3)
