from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pliris.retrieval.models import RetrievedChunk

NO_CONTEXT_MESSAGE = "No retrieved context is available."


@dataclass(frozen=True, slots=True)
class ContextSource:
    """Citation-ready source metadata for one included context block."""

    citation_id: str
    chunk_id: str
    title: str
    source: str
    page_start: int | None
    page_end: int | None
    page_label: str
    score: float
    rank: int
    document_id: str | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AssembledContext:
    """Deterministic prompt context plus its citation map."""

    text: str
    sources: tuple[ContextSource, ...]
    omitted_count: int
    character_count: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "sources": [source.to_dict() for source in self.sources],
            "omitted_count": self.omitted_count,
            "character_count": self.character_count,
            "truncated": self.truncated,
        }


class ContextAssembler:
    """Build citation-labelled prompt context from ranked chunks."""

    def __init__(
        self,
        *,
        max_chunks: int = 5,
        max_characters: int = 18_000,
        minimum_content_characters: int = 80,
    ) -> None:
        if max_chunks < 1:
            raise ValueError("max_chunks must be positive.")
        if max_characters < 200:
            raise ValueError("max_characters must be at least 200.")
        if minimum_content_characters < 1:
            raise ValueError("minimum_content_characters must be positive.")

        self.max_chunks = max_chunks
        self.max_characters = max_characters
        self.minimum_content_characters = minimum_content_characters

    def assemble(
        self,
        chunks: list[RetrievedChunk],
    ) -> AssembledContext:
        eligible = self._deduplicate(chunks)
        if not eligible:
            return AssembledContext(
                text=NO_CONTEXT_MESSAGE,
                sources=(),
                omitted_count=len(chunks),
                character_count=len(NO_CONTEXT_MESSAGE),
                truncated=False,
            )

        blocks: list[str] = []
        sources: list[ContextSource] = []
        truncated = False

        for chunk in eligible[: self.max_chunks]:
            citation_id = f"S{len(sources) + 1}"
            header = self._header(citation_id, chunk)
            separator_length = 2 if blocks else 0
            used = sum(len(block) for block in blocks)
            used += separator_length * len(blocks)
            remaining = self.max_characters - used

            available_content = remaining - len(header)
            if available_content < self.minimum_content_characters:
                truncated = True
                break

            content = chunk.text.strip()
            if len(content) > available_content:
                content = self._truncate(
                    content,
                    available_content,
                )
                truncated = True

            block = f"{header}{content}"
            blocks.append(block)
            sources.append(
                ContextSource(
                    citation_id=citation_id,
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    source=chunk.source,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    page_label=chunk.page_label,
                    score=chunk.score,
                    rank=chunk.rank,
                    document_id=chunk.document_id,
                    metadata=dict(chunk.metadata),
                )
            )

            if truncated:
                break

        context_text = "\n\n".join(blocks)
        omitted_count = max(0, len(eligible) - len(sources))

        return AssembledContext(
            text=context_text or NO_CONTEXT_MESSAGE,
            sources=tuple(sources),
            omitted_count=omitted_count,
            character_count=len(context_text or NO_CONTEXT_MESSAGE),
            truncated=truncated or omitted_count > 0,
        )

    @staticmethod
    def _deduplicate(
        chunks: list[RetrievedChunk],
    ) -> list[RetrievedChunk]:
        seen: set[str] = set()
        eligible: list[RetrievedChunk] = []

        for chunk in sorted(chunks, key=lambda item: item.rank):
            if not chunk.text.strip():
                continue
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            eligible.append(chunk)

        return eligible

    @staticmethod
    def _header(
        citation_id: str,
        chunk: RetrievedChunk,
    ) -> str:
        return (
            f"[{citation_id}]\n"
            f"Title: {chunk.title}\n"
            f"Source: {chunk.source}\n"
            f"Pages: {chunk.page_label}\n"
            f"Retrieval rank: {chunk.rank}\n"
            "Content:\n"
        )

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        if limit <= 3:
            return "." * limit

        candidate = text[: limit - 3].rstrip()
        last_space = candidate.rfind(" ")
        if last_space >= max(0, len(candidate) - 80):
            candidate = candidate[:last_space].rstrip()

        return f"{candidate}..."
