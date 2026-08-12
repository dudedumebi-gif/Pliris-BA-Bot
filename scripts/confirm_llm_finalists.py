from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from evaluation.llm_contexts import load_frozen_contexts
from evaluation.llm_contract import (
    contract_fingerprint,
    deterministic_output_root,
    load_evaluation_contract,
)
from evaluation.llm_finalist_contract import (
    finalist_contract_fingerprint,
    finalist_output_root,
    load_finalist_confirmation_contract,
)
from evaluation.llm_finalist_runner import (
    expected_finalist_api_calls,
    run_finalist_confirmation,
    validate_primary_evidence,
    validate_source_human_evidence,
)
from evaluation.llm_runner import PricingRates
from evaluation.llm_variant_generator import EvaluationGroundedGenerator


def _positive_rate(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("pricing rates must be greater than zero")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or run the controlled Phase 6 finalist confirmation."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--generation-input-price-per-million", type=_positive_rate)
    parser.add_argument("--generation-output-price-per-million", type=_positive_rate)
    return parser


def _require(value: float | None, option: str) -> float:
    if value is None:
        raise SystemExit(f"{option} is required with --execute.")
    return value


async def _main() -> None:
    args = _parser().parse_args()
    repo_root = Path.cwd()
    parent = load_evaluation_contract(repo_root)
    confirmation = load_finalist_confirmation_contract(repo_root, parent)
    validate_source_human_evidence(repo_root, parent, confirmation)

    parent_output = deterministic_output_root(repo_root, parent)
    context_path = parent_output / parent.config.outputs.frozen_contexts_jsonl
    bundle = load_frozen_contexts(context_path, parent)
    primary_records = validate_primary_evidence(
        parent,
        parent_output / parent.config.outputs.raw_outputs_jsonl,
    )
    paid_primary = sum(record.api_called for record in primary_records)
    expected_calls = expected_finalist_api_calls(parent, confirmation)
    output_root = finalist_output_root(repo_root, confirmation)

    if args.plan:
        print("parent_contract_fingerprint:", contract_fingerprint(parent))
        print("finalist_contract_fingerprint:", finalist_contract_fingerprint(confirmation))
        print("source_candidate:", confirmation.source_candidate_id)
        print("finalists:", ", ".join(confirmation.finalist_ids))
        print("cases:", len(parent.benchmark.cases))
        print("planned_attempts:", len(parent.benchmark.cases) * len(confirmation.variants))
        print("expected_generation_api_calls:", expected_calls)
        print("existing_primary_generation_api_calls:", paid_primary)
        print("projected_total_generation_api_calls:", paid_primary + expected_calls)
        print("max_total_live_calls:", parent.config.budget.max_total_live_calls)
        print("output_root:", output_root)
        print("production_prompt_changed: False")
        print("external_calls: 0")
        return

    generator = EvaluationGroundedGenerator(
        max_output_tokens=parent.config.generation.max_output_tokens,
        reasoning_effort=parent.config.generation.reasoning_effort,
        store=parent.config.generation.store,
    )
    summary = await run_finalist_confirmation(
        parent,
        confirmation,
        bundle,
        generator=generator,
        pricing_rates=PricingRates(
            generation_input_per_million=_require(
                args.generation_input_price_per_million,
                "--generation-input-price-per-million",
            ),
            generation_output_per_million=_require(
                args.generation_output_price_per_million,
                "--generation-output-price-per-million",
            ),
        ),
        repo_root=repo_root,
        output_root=output_root,
    )
    print("complete:", summary["complete"])
    print("recorded_attempts:", summary["recorded_attempts"])
    print("selection_status:", summary["selection_status"])
    print("estimated_total_cost_usd:", summary["budget"]["estimated_cost_usd"])
    print("summary:", output_root / confirmation.outputs.automated_summary_md)


if __name__ == "__main__":
    asyncio.run(_main())
