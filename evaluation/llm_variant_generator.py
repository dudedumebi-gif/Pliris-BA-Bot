from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from evaluation.llm_contract import PromptVariant, render_variant_instructions
from pliris.generation.context_assembler import AssembledContext
from pliris.generation.grounded_generator import (
    GROUNDED_RESPONSE_SCHEMA,
    GroundedResponseGenerator,
)
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedAnswer,
    GroundedDraft,
    GroundedResponseError,
    ResponseUsage,
)


@dataclass(frozen=True, slots=True)
class VariantGenerationResult:
    answer: GroundedAnswer
    raw_output_text: str
    api_called: bool


def instructions_for_variant(
    request_mode: str,
    variant: PromptVariant,
) -> str:
    base = GroundedResponseGenerator._instructions_for_mode(request_mode)
    return render_variant_instructions(base, variant)


def user_input_for_case(
    question: str,
    context: AssembledContext,
) -> str:
    return GroundedResponseGenerator._build_user_input(question, context)


class EvaluationGroundedGenerator(GroundedResponseGenerator):
    """Evaluation-only prompt injection around the production generator contract."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        settings: Any | None = None,
        validator: Any | None = None,
        max_output_tokens: int = 2_400,
        reasoning_effort: str = "low",
        store: bool = False,
    ) -> None:
        super().__init__(
            client=client,
            settings=settings,
            validator=validator,
            max_output_tokens=max_output_tokens,
        )
        normalized_effort = reasoning_effort.strip()
        if not normalized_effort:
            raise ValueError("reasoning_effort must not be blank")
        self.reasoning_effort = normalized_effort
        self.store = bool(store)

    async def generate_variant(
        self,
        *,
        question: str,
        context: AssembledContext,
        request_mode: str,
        variant: PromptVariant,
        model: str,
    ) -> VariantGenerationResult:
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be blank")
        normalized_model = model.strip()
        if not normalized_model:
            raise ValueError("model must not be blank")

        if not context.sources:
            draft = GroundedDraft(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                citation_ids=(),
                insufficient_evidence=True,
            )
            answer = self.validator.validate(
                draft,
                context,
                model=normalized_model,
                response_id=None,
                usage=ResponseUsage(),
            )
            raw = json.dumps(
                {
                    "answer": answer.answer,
                    "citation_ids": [],
                    "insufficient_evidence": True,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            return VariantGenerationResult(
                answer=answer,
                raw_output_text=raw,
                api_called=False,
            )

        response = await self.client.responses.create(
            model=normalized_model,
            instructions=instructions_for_variant(
                request_mode,
                variant,
            ),
            input=user_input_for_case(
                normalized_question,
                context,
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "pliris_grounded_answer",
                    "description": ("A context-grounded answer with validated source identifiers."),
                    "strict": True,
                    "schema": GROUNDED_RESPONSE_SCHEMA,
                }
            },
            max_output_tokens=self.max_output_tokens,
            reasoning={"effort": self.reasoning_effort},
            store=self.store,
        )

        status = getattr(response, "status", None)
        if status not in (None, "completed"):
            incomplete_details = getattr(
                response,
                "incomplete_details",
                None,
            )
            incomplete_reason = self._value(
                incomplete_details,
                "reason",
            )
            detail = f"; reason={incomplete_reason!r}" if incomplete_reason else ""
            raise GroundedResponseError(f"OpenAI response did not complete: {status!r}{detail}.")

        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            raise GroundedResponseError("OpenAI response contained no output text.")

        draft = self._parse_draft(output_text)
        response_model = str(getattr(response, "model", normalized_model) or normalized_model)
        answer = self.validator.validate(
            draft,
            context,
            model=response_model,
            response_id=self._optional_string(getattr(response, "id", None)),
            usage=self._extract_usage(getattr(response, "usage", None)),
        )
        return VariantGenerationResult(
            answer=answer,
            raw_output_text=output_text,
            api_called=True,
        )
