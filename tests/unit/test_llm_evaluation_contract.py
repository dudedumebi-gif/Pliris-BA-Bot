from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.llm_contract import (
    ContextStrategy,
    EvaluationConfig,
    GenerationBenchmark,
    PromptVariantSet,
    RequestMode,
    contract_fingerprint,
    deterministic_output_root,
    load_evaluation_contract,
    render_variant_instructions,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_contract():
    return load_evaluation_contract(REPO_ROOT)


def test_loads_frozen_phase6_contract() -> None:
    contract = load_contract()

    assert contract.config.model == "gpt-5-mini"
    assert len(contract.prompt_variants.variants) == 3
    assert len(contract.benchmark.cases) == 12
    assert contract.primary_live_calls == 36
    assert contract.maximum_live_calls == 60


def test_benchmark_covers_every_mode_and_context_strategy() -> None:
    contract = load_contract()

    modes = {case.request_mode for case in contract.benchmark.cases}
    strategies = {case.context_strategy for case in contract.benchmark.cases}

    assert modes == set(RequestMode)
    assert strategies == set(ContextStrategy)


def test_benchmark_rejects_duplicate_case_ids() -> None:
    contract = load_contract()
    payload = contract.benchmark.model_dump(mode="json")
    payload["cases"].append(payload["cases"][0])

    with pytest.raises(
        ValidationError,
        match="benchmark case ids must be unique",
    ):
        GenerationBenchmark.model_validate(payload)


def test_source_conflict_requires_two_synthetic_sources() -> None:
    contract = load_contract()
    payload = contract.benchmark.model_dump(mode="json")
    conflict_case = next(
        case for case in payload["cases"] if case["request_mode"] == "source_conflict_review"
    )
    conflict_case["synthetic_chunks"] = conflict_case["synthetic_chunks"][:1]

    with pytest.raises(
        ValidationError,
        match="at least two synthetic chunks",
    ):
        GenerationBenchmark.model_validate(payload)


def test_empty_context_requires_exact_insufficient_evidence_contract() -> None:
    contract = load_contract()
    payload = contract.benchmark.model_dump(mode="json")
    empty_case = next(case for case in payload["cases"] if case["context_strategy"] == "empty")
    empty_case["expected_exact_answer"] = None

    with pytest.raises(
        ValidationError,
        match="expected_exact_answer",
    ):
        GenerationBenchmark.model_validate(payload)


def test_prompt_variants_have_one_unchanged_production_baseline() -> None:
    contract = load_contract()
    baselines = [
        variant for variant in contract.prompt_variants.variants if variant.is_production_baseline
    ]

    assert len(baselines) == 1
    assert baselines[0].id == "production_baseline_v1"
    assert baselines[0].additional_instructions == ""


def test_prompt_variant_set_rejects_multiple_baselines() -> None:
    contract = load_contract()
    payload = contract.prompt_variants.model_dump(mode="json")
    payload["variants"][1]["is_production_baseline"] = True
    payload["variants"][1]["additional_instructions"] = ""

    with pytest.raises(
        ValidationError,
        match="exactly one production baseline",
    ):
        PromptVariantSet.model_validate(payload)


def test_variant_rendering_preserves_baseline_and_appends_candidates() -> None:
    contract = load_contract()
    variants = {variant.id: variant for variant in contract.prompt_variants.variants}
    base = "Use only supplied evidence."

    assert (
        render_variant_instructions(
            base,
            variants["production_baseline_v1"],
        )
        == base
    )
    rendered = render_variant_instructions(
        base,
        variants["evidence_first_v1"],
    )
    assert rendered.startswith(base)
    assert "identify which requested claims" in rendered


def test_config_rejects_scoring_weights_that_do_not_sum_to_one() -> None:
    contract = load_contract()
    payload = contract.config.model_dump(mode="json")
    payload["scoring_dimensions"][0]["weight"] = 0.20

    with pytest.raises(
        ValidationError,
        match=r"weights must sum to 1\.0",
    ):
        EvaluationConfig.model_validate(payload)


def test_contract_fingerprint_and_output_root_are_deterministic() -> None:
    contract = load_contract()

    first = contract_fingerprint(contract)
    second = contract_fingerprint(load_contract())
    output_root = deterministic_output_root(REPO_ROOT, contract)

    assert first == second
    assert len(first) == 64
    assert output_root == (REPO_ROOT / "artifacts/llm_evaluation/v1/gpt-5-mini").resolve()
