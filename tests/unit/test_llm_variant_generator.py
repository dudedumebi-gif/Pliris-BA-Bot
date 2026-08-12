from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.llm_contract import load_evaluation_contract
from evaluation.llm_variant_generator import (
    EvaluationGroundedGenerator,
)
from pliris.generation.context_assembler import ContextAssembler
from pliris.generation.grounded_generator import (
    GROUNDED_SYSTEM_INSTRUCTIONS,
)
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedResponseValidationError,
)
from pliris.retrieval.models import RetrievedChunk

REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeResponses:
    def __init__(self, output_text: str):
        self.output_text = output_text
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="resp-eval",
            model="gpt-5-mini",
            status="completed",
            output_text=self.output_text,
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
            ),
        )


class FakeClient:
    def __init__(self, output_text: str):
        self.responses = FakeResponses(output_text)


def settings():
    return SimpleNamespace(
        openai_chat_model="gpt-5-mini",
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
    )


def context():
    return ContextAssembler().assemble(
        [
            RetrievedChunk(
                rank=1,
                chunk_id="chunk-1",
                text="Requirements have traceable lineage.",
                title="Source",
                source="source",
                page_start=1,
                page_end=1,
                score=1.0,
                document_id="doc",
                metadata={},
            )
        ]
    )


def variants():
    contract = load_evaluation_contract(REPO_ROOT)
    return {variant.id: variant for variant in contract.prompt_variants.variants}


@pytest.mark.asyncio
async def test_baseline_uses_unchanged_production_instructions() -> None:
    client = FakeClient(
        json.dumps(
            {
                "answer": "Traceability records lineage [S1].",
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        )
    )
    generator = EvaluationGroundedGenerator(
        client=client,
        settings=settings(),
    )

    await generator.generate_variant(
        question="What is traceability?",
        context=context(),
        request_mode="grounded_question",
        variant=variants()["production_baseline_v1"],
        model="gpt-5-mini",
    )

    assert client.responses.calls[0]["instructions"] == GROUNDED_SYSTEM_INSTRUCTIONS


@pytest.mark.asyncio
async def test_candidate_instructions_append_without_replacing_mode_profile() -> None:
    client = FakeClient(
        json.dumps(
            {
                "answer": "Traceability records lineage [S1].",
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        )
    )
    generator = EvaluationGroundedGenerator(
        client=client,
        settings=settings(),
    )

    await generator.generate_variant(
        question="Compare approaches.",
        context=context(),
        request_mode="framework_comparison",
        variant=variants()["evidence_first_v1"],
        model="gpt-5-mini",
    )

    instructions = client.responses.calls[0]["instructions"]
    assert "framework-comparison requests" in instructions
    assert "identify which requested claims" in instructions


@pytest.mark.asyncio
async def test_empty_context_skips_paid_api_call() -> None:
    client = FakeClient("unused")
    generator = EvaluationGroundedGenerator(
        client=client,
        settings=settings(),
    )

    result = await generator.generate_variant(
        question="Unknown threshold?",
        context=ContextAssembler().assemble([]),
        request_mode="grounded_question",
        variant=variants()["production_baseline_v1"],
        model="gpt-5-mini",
    )

    assert result.api_called is False
    assert result.answer.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert client.responses.calls == []


@pytest.mark.asyncio
async def test_invalid_json_remains_a_validation_failure() -> None:
    generator = EvaluationGroundedGenerator(
        client=FakeClient("not-json"),
        settings=settings(),
    )

    with pytest.raises(
        GroundedResponseValidationError,
        match="not valid JSON",
    ):
        await generator.generate_variant(
            question="What is traceability?",
            context=context(),
            request_mode="grounded_question",
            variant=variants()["production_baseline_v1"],
            model="gpt-5-mini",
        )
