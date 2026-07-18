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
    GROUNDED_RESPONSE_SCHEMA,
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
    assert call["text"]["format"]["schema"] == GROUNDED_RESPONSE_SCHEMA
    assert call["text"]["format"]["strict"] is True
    assert "[S1]" in call["input"]


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
