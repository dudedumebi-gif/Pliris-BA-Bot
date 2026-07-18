from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from pliris.generation.context_assembler import (
    AssembledContext,
    ContextAssembler,
)
from pliris.generation.grounded_generator import (
    DELIVERABLE_OUTLINE_INSTRUCTIONS,
    FRAMEWORK_COMPARISON_INSTRUCTIONS,
    GROUNDED_RESPONSE_SCHEMA,
    GROUNDED_SYSTEM_INSTRUCTIONS,
    SCENARIO_ANALYSIS_INSTRUCTIONS,
    SOURCE_CONFLICT_REVIEW_INSTRUCTIONS,
    GroundedResponseGenerator,
)
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedResponseError,
    GroundedResponseValidationError,
)
from pliris.retrieval.models import RetrievedChunk


class FakeResponses:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response: Any) -> None:
        self.responses = FakeResponses(response)


def context_with_source() -> AssembledContext:
    return ContextAssembler().assemble(
        [
            RetrievedChunk(
                rank=1,
                chunk_id="chunk-1",
                text=("Requirements traceability identifies and documents requirement lineage."),
                title="BABOK Guide",
                source="babok-v3",
                page_start=87,
                page_end=91,
                score=0.038,
                document_id="doc-1",
                metadata={"manifest_document_id": "babok-v3"},
            )
        ]
    )


def context_with_conflicting_sources() -> AssembledContext:
    return ContextAssembler().assemble(
        [
            RetrievedChunk(
                rank=1,
                chunk_id="chunk-1",
                text=("Source A recommends retaining an approved requirements baseline."),
                title="Source A",
                source="source-a",
                page_start=10,
                page_end=10,
                score=0.041,
                document_id="doc-1",
                metadata={"manifest_document_id": "source-a"},
            ),
            RetrievedChunk(
                rank=2,
                chunk_id="chunk-2",
                text=("Source B recommends replacing the approved requirements baseline."),
                title="Source B",
                source="source-b",
                page_start=20,
                page_end=20,
                score=0.039,
                document_id="doc-2",
                metadata={"manifest_document_id": "source-b"},
            ),
        ]
    )


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        openai_chat_model="gpt-5-mini",
        openai_api_key=SimpleNamespace(get_secret_value=lambda: "test-key"),
    )


@pytest.mark.asyncio
async def test_generator_uses_responses_api_structured_output() -> None:
    response = SimpleNamespace(
        id="resp-123",
        model="gpt-5-mini-2026-01-01",
        status="completed",
        output_text=json.dumps(
            {
                "answer": ("Requirements traceability records the lineage of requirements [S1]."),
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        ),
        usage=SimpleNamespace(
            input_tokens=200,
            output_tokens=50,
            total_tokens=250,
        ),
    )
    client = FakeClient(response)
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    answer = await generator.generate(
        question="What is requirements traceability?",
        context=context_with_source(),
    )

    assert answer.response_id == "resp-123"
    assert answer.model == "gpt-5-mini-2026-01-01"
    assert answer.citation_ids == ("S1",)
    assert answer.usage.total_tokens == 250

    call = client.responses.calls[0]
    assert call["model"] == "gpt-5-mini"
    assert call["store"] is False
    assert call["max_output_tokens"] == 2_400
    assert call["reasoning"] == {"effort": "low"}
    assert call["instructions"] == GROUNDED_SYSTEM_INSTRUCTIONS
    assert call["text"]["format"]["schema"] == GROUNDED_RESPONSE_SCHEMA
    assert call["text"]["format"]["strict"] is True
    assert "[S1]" in call["input"]


@pytest.mark.asyncio
async def test_generator_adds_framework_comparison_instructions() -> None:
    response = SimpleNamespace(
        id="resp-framework",
        model="gpt-5-mini",
        status="completed",
        output_text=json.dumps(
            {
                "answer": ("The approaches share a traceability focus [S1]."),
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        ),
        usage={},
    )
    client = FakeClient(response)
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    await generator.generate(
        question="Compare two requirements approaches.",
        context=context_with_source(),
        request_mode="framework_comparison",
    )

    instructions = client.responses.calls[0]["instructions"]
    assert GROUNDED_SYSTEM_INSTRUCTIONS in instructions
    assert FRAMEWORK_COMPARISON_INSTRUCTIONS in instructions
    assert "Do not declare an overall winner" in instructions


@pytest.mark.asyncio
async def test_generator_adds_scenario_analysis_instructions() -> None:
    response = SimpleNamespace(
        id="resp-scenario",
        model="gpt-5-mini",
        status="completed",
        output_text=json.dumps(
            {
                "answer": ("If the scenario occurs, traceability may be affected [S1]."),
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        ),
        usage={},
    )
    client = FakeClient(response)
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    await generator.generate(
        question=("What if a requirement changes after approval?"),
        context=context_with_source(),
        request_mode="scenario_analysis",
    )

    instructions = client.responses.calls[0]["instructions"]
    assert GROUNDED_SYSTEM_INSTRUCTIONS in instructions
    assert SCENARIO_ANALYSIS_INSTRUCTIONS in instructions
    assert FRAMEWORK_COMPARISON_INSTRUCTIONS not in instructions
    assert "Do not present a hypothetical outcome" in instructions
    assert "Do not assign" in instructions


@pytest.mark.asyncio
async def test_generator_adds_deliverable_outline_instructions() -> None:
    response = SimpleNamespace(
        id="resp-outline",
        model="gpt-5-mini",
        status="completed",
        output_text=json.dumps(
            {
                "answer": ("The outline should include a traceability section [S1]."),
                "citation_ids": ["S1"],
                "insufficient_evidence": False,
            }
        ),
        usage={},
    )
    client = FakeClient(response)
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    await generator.generate(
        question="Outline a requirements traceability deliverable.",
        context=context_with_source(),
        request_mode="deliverable_outline",
    )

    instructions = client.responses.calls[0]["instructions"]
    assert GROUNDED_SYSTEM_INSTRUCTIONS in instructions
    assert DELIVERABLE_OUTLINE_INSTRUCTIONS in instructions
    assert FRAMEWORK_COMPARISON_INSTRUCTIONS not in instructions
    assert SCENARIO_ANALYSIS_INSTRUCTIONS not in instructions
    assert "suggested placeholders" in instructions
    assert "Do not invent names, owners, dates" in instructions
    normalized_instructions = " ".join(instructions.split())
    assert "Do not present the outline as a finished deliverable" in normalized_instructions


@pytest.mark.asyncio
async def test_generator_adds_source_conflict_review_instructions() -> None:
    response = SimpleNamespace(
        id="resp-conflict",
        model="gpt-5-mini",
        status="completed",
        output_text=json.dumps(
            {
                "answer": (
                    "Source A supports retaining the baseline [S1], "
                    "while Source B supports replacing it [S2]. "
                    "The available evidence does not resolve the "
                    "conflict."
                ),
                "citation_ids": ["S1", "S2"],
                "insufficient_evidence": False,
            }
        ),
        usage={},
    )
    client = FakeClient(response)
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    answer = await generator.generate(
        question="Review the conflict between these sources.",
        context=context_with_conflicting_sources(),
        request_mode="source_conflict_review",
    )

    assert answer.citation_ids == ("S1", "S2")
    instructions = client.responses.calls[0]["instructions"]
    assert GROUNDED_SYSTEM_INSTRUCTIONS in instructions
    assert SOURCE_CONFLICT_REVIEW_INSTRUCTIONS in instructions
    assert FRAMEWORK_COMPARISON_INSTRUCTIONS not in instructions
    assert SCENARIO_ANALYSIS_INSTRUCTIONS not in instructions
    assert DELIVERABLE_OUTLINE_INSTRUCTIONS not in instructions
    normalized_instructions = " ".join(instructions.split())
    assert "Cite each source's position independently" in (normalized_instructions)
    assert "Do not blend incompatible claims into a false consensus" in (normalized_instructions)
    assert "state that the conflict remains unresolved" in (normalized_instructions)


@pytest.mark.asyncio
async def test_generator_skips_api_when_context_is_empty() -> None:
    client = FakeClient(
        SimpleNamespace(
            status="completed",
            output_text="unused",
        )
    )
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    answer = await generator.generate(
        question="What is an unknown practice?",
        context=ContextAssembler().assemble([]),
    )

    assert answer.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert answer.insufficient_evidence is True
    assert client.responses.calls == []


@pytest.mark.asyncio
async def test_generator_rejects_invalid_json_output() -> None:
    client = FakeClient(
        SimpleNamespace(
            id="resp-invalid",
            model="gpt-5-mini",
            status="completed",
            output_text="not-json",
            usage=None,
        )
    )
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    with pytest.raises(
        GroundedResponseValidationError,
        match="not valid JSON",
    ):
        await generator.generate(
            question="What is traceability?",
            context=context_with_source(),
        )


@pytest.mark.asyncio
async def test_generator_rejects_incomplete_response() -> None:
    client = FakeClient(
        SimpleNamespace(
            id="resp-incomplete",
            model="gpt-5-mini",
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_text="",
            usage=None,
        )
    )
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    with pytest.raises(
        GroundedResponseError,
        match="reason='max_output_tokens'",
    ):
        await generator.generate(
            question="What is traceability?",
            context=context_with_source(),
        )


@pytest.mark.asyncio
async def test_generator_rejects_unknown_model_citation() -> None:
    client = FakeClient(
        SimpleNamespace(
            id="resp-unknown",
            model="gpt-5-mini",
            status="completed",
            output_text=json.dumps(
                {
                    "answer": "Unsupported claim [S9].",
                    "citation_ids": ["S9"],
                    "insufficient_evidence": False,
                }
            ),
            usage={},
        )
    )
    generator = GroundedResponseGenerator(
        client=client,
        settings=settings(),
    )

    with pytest.raises(
        GroundedResponseValidationError,
        match="Unknown citation identifiers: S9",
    ):
        await generator.generate(
            question="What is traceability?",
            context=context_with_source(),
        )


@pytest.mark.asyncio
async def test_generator_validates_question_and_token_limit() -> None:
    with pytest.raises(
        ValueError,
        match="max_output_tokens must be at least 100",
    ):
        GroundedResponseGenerator(
            client=FakeClient(None),
            settings=settings(),
            max_output_tokens=99,
        )

    generator = GroundedResponseGenerator(
        client=FakeClient(None),
        settings=settings(),
    )
    with pytest.raises(
        ValueError,
        match="question must not be blank",
    ):
        await generator.generate(
            question="   ",
            context=context_with_source(),
        )
