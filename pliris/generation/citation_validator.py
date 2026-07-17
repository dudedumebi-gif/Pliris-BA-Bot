from __future__ import annotations

import re

from pliris.generation.context_assembler import AssembledContext
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedAnswer,
    GroundedDraft,
    GroundedResponseValidationError,
    ResponseUsage,
)


_CITATION_TOKEN_PATTERN = re.compile(r"\[S[^\]]+\]")
_EXACT_CITATION_PATTERN = re.compile(r"\[(S[1-9]\d*)\]")


class CitationValidator:
    """Validate citation integrity and map source IDs to source metadata."""

    def validate(
        self,
        draft: GroundedDraft,
        context: AssembledContext,
        *,
        model: str,
        response_id: str | None,
        usage: ResponseUsage,
    ) -> GroundedAnswer:
        answer = draft.answer.strip()
        if draft.insufficient_evidence:
            return self._validate_insufficient(
                draft,
                context,
                model=model,
                response_id=response_id,
                usage=usage,
            )

        if not answer:
            raise GroundedResponseValidationError(
                "A grounded answer cannot be blank."
            )
        if not context.sources:
            raise GroundedResponseValidationError(
                "A grounded answer cannot be returned without sources."
            )

        inline_ids = self._extract_inline_ids(answer)
        declared_ids = self._normalize_declared_ids(
            draft.citation_ids
        )
        available = {
            source.citation_id: source
            for source in context.sources
        }

        unknown_ids = sorted(
            (set(inline_ids) | set(declared_ids))
            - set(available)
        )
        if unknown_ids:
            raise GroundedResponseValidationError(
                "Unknown citation identifiers: "
                + ", ".join(unknown_ids)
            )

        if not inline_ids:
            raise GroundedResponseValidationError(
                "A supported answer must contain at least one "
                "inline citation."
            )
        if inline_ids != declared_ids:
            raise GroundedResponseValidationError(
                "Declared citation identifiers must match their "
                "first appearance in the answer."
            )

        citations = tuple(
            available[citation_id]
            for citation_id in declared_ids
        )
        return GroundedAnswer(
            answer=answer,
            citation_ids=tuple(declared_ids),
            citations=citations,
            insufficient_evidence=False,
            model=model,
            response_id=response_id,
            usage=usage,
            metadata={
                "available_source_count": len(context.sources),
                "context_truncated": context.truncated,
                "context_character_count": (
                    context.character_count
                ),
            },
        )

    def _validate_insufficient(
        self,
        draft: GroundedDraft,
        context: AssembledContext,
        *,
        model: str,
        response_id: str | None,
        usage: ResponseUsage,
    ) -> GroundedAnswer:
        if draft.answer.strip() != INSUFFICIENT_EVIDENCE_MESSAGE:
            raise GroundedResponseValidationError(
                "Insufficient-evidence responses must use the "
                "approved fallback message."
            )
        if draft.citation_ids:
            raise GroundedResponseValidationError(
                "Insufficient-evidence responses cannot cite sources."
            )
        if _CITATION_TOKEN_PATTERN.search(draft.answer):
            raise GroundedResponseValidationError(
                "Insufficient-evidence responses cannot contain "
                "inline citations."
            )

        return GroundedAnswer(
            answer=INSUFFICIENT_EVIDENCE_MESSAGE,
            citation_ids=(),
            citations=(),
            insufficient_evidence=True,
            model=model,
            response_id=response_id,
            usage=usage,
            metadata={
                "available_source_count": len(context.sources),
                "context_truncated": context.truncated,
                "context_character_count": (
                    context.character_count
                ),
            },
        )

    @staticmethod
    def _normalize_declared_ids(
        citation_ids: tuple[str, ...],
    ) -> list[str]:
        normalized: list[str] = []
        for raw_id in citation_ids:
            citation_id = str(raw_id).strip()
            if citation_id not in normalized:
                normalized.append(citation_id)
        return normalized

    @staticmethod
    def _extract_inline_ids(answer: str) -> list[str]:
        tokens = _CITATION_TOKEN_PATTERN.findall(answer)
        citation_ids: list[str] = []

        for token in tokens:
            match = _EXACT_CITATION_PATTERN.fullmatch(token)
            if match is None:
                raise GroundedResponseValidationError(
                    f"Malformed citation token: {token}"
                )
            citation_id = match.group(1)
            if citation_id not in citation_ids:
                citation_ids.append(citation_id)

        return citation_ids
