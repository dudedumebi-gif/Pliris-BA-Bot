from __future__ import annotations

import json
from typing import Any

from pliris.generation.citation_validator import CitationValidator
from pliris.generation.context_assembler import AssembledContext
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedAnswer,
    GroundedDraft,
    GroundedResponseError,
    GroundedResponseValidationError,
    ResponseUsage,
)


GROUNDED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "answer": {"type": "string"},
        "citation_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "insufficient_evidence": {"type": "boolean"},
    },
    "required": [
        "answer",
        "citation_ids",
        "insufficient_evidence",
    ],
}


GROUNDED_SYSTEM_INSTRUCTIONS = f"""
You are Pliris BA Bot, a grounded Business Analysis, Business Systems
Analysis, and Project Management assistant.

Use only the supplied knowledge-base context. Do not rely on unstated
general knowledge.

For every substantive factual claim, add one or more inline citations
using the exact available source identifiers, such as [S1] or [S2].
Never invent a source identifier. Do not create a references section.

The citation_ids field must list each cited source identifier once, in
the order of its first appearance in the answer.

When the supplied context does not contain enough evidence, set
insufficient_evidence to true, set citation_ids to an empty list, and
return this exact answer:
{INSUFFICIENT_EVIDENCE_MESSAGE}
""".strip()


class GroundedResponseGenerator:
    """Generate and validate a context-only answer with the Responses API."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        settings: Any | None = None,
        validator: CitationValidator | None = None,
        max_output_tokens: int = 1_200,
    ) -> None:
        if max_output_tokens < 100:
            raise ValueError(
                "max_output_tokens must be at least 100."
            )

        if settings is None:
            from pliris.config.settings import get_settings

            settings = get_settings()

        if client is None:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=(
                    settings.openai_api_key.get_secret_value()
                )
            )

        self.client = client
        self.settings = settings
        self.validator = validator or CitationValidator()
        self.max_output_tokens = max_output_tokens

    async def generate(
        self,
        *,
        question: str,
        context: AssembledContext,
        model: str | None = None,
    ) -> GroundedAnswer:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be blank.")

        selected_model = model or self.settings.openai_model

        if not context.sources:
            return self.validator.validate(
                GroundedDraft(
                    answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                    citation_ids=(),
                    insufficient_evidence=True,
                ),
                context,
                model=selected_model,
                response_id=None,
                usage=ResponseUsage(),
            )

        response = await self.client.responses.create(
            model=selected_model,
            instructions=GROUNDED_SYSTEM_INSTRUCTIONS,
            input=self._build_user_input(
                normalized_question,
                context,
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "pliris_grounded_answer",
                    "description": (
                        "A context-grounded answer with validated "
                        "source identifiers."
                    ),
                    "strict": True,
                    "schema": GROUNDED_RESPONSE_SCHEMA,
                }
            },
            max_output_tokens=self.max_output_tokens,
            store=False,
        )

        status = getattr(response, "status", None)
        if status not in (None, "completed"):
            raise GroundedResponseError(
                f"OpenAI response did not complete: {status!r}."
            )

        output_text = str(
            getattr(response, "output_text", "") or ""
        ).strip()
        if not output_text:
            raise GroundedResponseError(
                "OpenAI response contained no output text."
            )

        draft = self._parse_draft(output_text)
        response_model = str(
            getattr(response, "model", selected_model)
            or selected_model
        )
        return self.validator.validate(
            draft,
            context,
            model=response_model,
            response_id=self._optional_string(
                getattr(response, "id", None)
            ),
            usage=self._extract_usage(
                getattr(response, "usage", None)
            ),
        )

    @staticmethod
    def _build_user_input(
        question: str,
        context: AssembledContext,
    ) -> str:
        return (
            "USER QUESTION\n"
            f"{question}\n\n"
            "KNOWLEDGE-BASE CONTEXT\n"
            f"{context.text}\n\n"
            "Return the structured grounded answer."
        )

    @staticmethod
    def _parse_draft(output_text: str) -> GroundedDraft:
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise GroundedResponseValidationError(
                "OpenAI response was not valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise GroundedResponseValidationError(
                "OpenAI response must be a JSON object."
            )

        answer = payload.get("answer")
        citation_ids = payload.get("citation_ids")
        insufficient = payload.get("insufficient_evidence")

        if not isinstance(answer, str):
            raise GroundedResponseValidationError(
                "The answer field must be a string."
            )
        if not isinstance(citation_ids, list) or not all(
            isinstance(item, str) for item in citation_ids
        ):
            raise GroundedResponseValidationError(
                "The citation_ids field must be a list of strings."
            )
        if not isinstance(insufficient, bool):
            raise GroundedResponseValidationError(
                "The insufficient_evidence field must be boolean."
            )

        return GroundedDraft(
            answer=answer,
            citation_ids=tuple(citation_ids),
            insufficient_evidence=insufficient,
        )

    @classmethod
    def _extract_usage(cls, usage: Any) -> ResponseUsage:
        return ResponseUsage(
            input_tokens=cls._optional_int(
                cls._value(usage, "input_tokens")
            ),
            output_tokens=cls._optional_int(
                cls._value(usage, "output_tokens")
            ),
            total_tokens=cls._optional_int(
                cls._value(usage, "total_tokens")
            ),
        )

    @staticmethod
    def _value(container: Any, name: str) -> Any:
        if container is None:
            return None
        if isinstance(container, dict):
            return container.get(name)
        return getattr(container, name, None)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)
