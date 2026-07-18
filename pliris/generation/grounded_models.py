from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pliris.generation.context_assembler import ContextSource

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The available knowledge base does not contain enough evidence to answer this question."
)


class GroundedResponseError(RuntimeError):
    """Base error for grounded response generation."""


class GroundedResponseValidationError(GroundedResponseError):
    """Raised when model output violates the grounding contract."""


@dataclass(frozen=True, slots=True)
class ResponseUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, int | None]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GroundedDraft:
    answer: str
    citation_ids: tuple[str, ...]
    insufficient_evidence: bool


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    answer: str
    citation_ids: tuple[str, ...]
    citations: tuple[ContextSource, ...]
    insufficient_evidence: bool
    model: str
    response_id: str | None
    usage: ResponseUsage
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citation_ids": list(self.citation_ids),
            "citations": [citation.to_dict() for citation in self.citations],
            "insufficient_evidence": self.insufficient_evidence,
            "model": self.model,
            "response_id": self.response_id,
            "usage": self.usage.to_dict(),
            "metadata": dict(self.metadata),
        }
