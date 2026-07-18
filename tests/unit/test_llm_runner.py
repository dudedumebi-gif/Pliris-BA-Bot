from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.llm_contexts import freeze_contexts
from evaluation.llm_contract import load_evaluation_contract
from evaluation.llm_runner import (
    BudgetExceeded,
    BudgetLedger,
    PricingRates,
    aggregate_records,
    build_run_plan,
    estimate_text_tokens,
    expected_generation_api_calls,
    load_latest_records,
    run_primary_comparison,
)
from evaluation.llm_variant_generator import VariantGenerationResult
from pliris.generation.grounded_models import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedAnswer,
    ResponseUsage,
)
from pliris.retrieval.models import RetrievedChunk

REPO_ROOT = Path(__file__).resolve().parents[2]


def contract():
    return load_evaluation_contract(REPO_ROOT)


class BenchmarkRetriever:
    def __init__(self, active):
        self.active = active

    async def search(
        self,
        query,
        *,
        top_k,
        document_id,
    ):
        case = next(item for item in self.active.benchmark.cases if item.retrieval_query == query)
        page = case.expected_page_ranges[0]
        return [
            RetrievedChunk(
                rank=1,
                chunk_id=f"{case.id}-1",
                text=" ".join(group[0] for group in case.required_term_groups),
                title="Source",
                source="source",
                page_start=page.start,
                page_end=page.end,
                score=1.0,
                document_id="doc",
                metadata={},
            )
        ]


class FakeGenerator:
    def __init__(self):
        self.calls = 0

    async def generate_variant(
        self,
        *,
        question,
        context,
        request_mode,
        variant,
        model,
    ):
        if not context.sources:
            generated = GroundedAnswer(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                citation_ids=(),
                citations=(),
                insufficient_evidence=True,
                model=model,
                response_id=None,
                usage=ResponseUsage(),
                metadata={},
            )
            return VariantGenerationResult(
                answer=generated,
                raw_output_text="local fallback",
                api_called=False,
            )

        self.calls += 1
        citation_ids = tuple(source.citation_id for source in context.sources[:2])
        generated = GroundedAnswer(
            answer=(
                "The evidence describes requirements, assumptions, "
                "different scope, and an unresolved decision "
                + " ".join(f"[{item}]" for item in citation_ids)
            ),
            citation_ids=citation_ids,
            citations=tuple(context.sources[:2]),
            insufficient_evidence=False,
            model=model,
            response_id=f"resp-{self.calls}",
            usage=ResponseUsage(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            ),
            metadata={},
        )
        return VariantGenerationResult(
            answer=generated,
            raw_output_text="raw",
            api_called=True,
        )


def rates():
    return PricingRates(
        generation_input_per_million=1.0,
        generation_output_per_million=1.0,
    )


def test_run_plan_is_counterbalanced_and_complete() -> None:
    active = contract()
    plan = build_run_plan(active)

    assert len(plan) == 36
    assert plan[0].variant_id == "production_baseline_v1"
    assert plan[3].variant_id == "evidence_first_v1"
    assert len({item.attempt_id for item in plan}) == 36
    assert expected_generation_api_calls(active) == 33


def test_budget_preflight_stops_before_excess_call() -> None:
    active = contract()
    ledger = BudgetLedger(active, rates())
    ledger.generation_api_calls = active.config.budget.max_primary_live_calls

    with pytest.raises(
        BudgetExceeded,
        match="call budget",
    ):
        ledger.preflight_generation(
            estimated_input_tokens=10,
            maximum_output_tokens=10,
        )


def test_token_estimation_is_positive_and_deterministic() -> None:
    first = estimate_text_tokens(
        "Requirements traceability",
        "gpt-5-mini",
    )
    second = estimate_text_tokens(
        "Requirements traceability",
        "gpt-5-mini",
    )

    assert first > 0
    assert first == second


def test_empty_aggregate_explicitly_avoids_prompt_selection() -> None:
    active = contract()
    summary = aggregate_records(
        active,
        {},
        BudgetLedger(active, rates()).snapshot(),
    )

    assert summary["selection_status"] == "not_performed_phase_6_step_2"
    assert summary["complete"] is False
    assert len(summary["variants"]) == 3


@pytest.mark.asyncio
async def test_runner_resumes_successful_attempts_without_duplicate_calls(
    tmp_path: Path,
) -> None:
    active = contract()
    bundle = await freeze_contexts(
        active,
        retriever=BenchmarkRetriever(active),
    )
    generator = FakeGenerator()

    first = await run_primary_comparison(
        active,
        bundle,
        generator=generator,
        pricing_rates=rates(),
        output_root=tmp_path,
    )
    calls_after_first = generator.calls

    second = await run_primary_comparison(
        active,
        bundle,
        generator=generator,
        pricing_rates=rates(),
        output_root=tmp_path,
    )
    raw_path = tmp_path / active.config.outputs.raw_outputs_jsonl
    latest = load_latest_records(
        raw_path,
        first["contract_fingerprint"],
    )

    assert first["complete"] is True
    assert second["complete"] is True
    assert calls_after_first == 33
    assert generator.calls == calls_after_first
    assert len(latest) == 36
