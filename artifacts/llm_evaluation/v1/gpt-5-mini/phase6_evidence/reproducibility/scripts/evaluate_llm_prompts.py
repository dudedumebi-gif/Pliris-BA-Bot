from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from evaluation.llm_contexts import (
    MeteredEmbeddingService,
    freeze_contexts,
    load_frozen_contexts,
    write_frozen_contexts,
)
from evaluation.llm_contract import (
    contract_fingerprint,
    deterministic_output_root,
    load_evaluation_contract,
)
from evaluation.llm_runner import (
    PricingRates,
    estimate_text_tokens,
    expected_generation_api_calls,
    run_primary_comparison,
)
from evaluation.llm_variant_generator import (
    EvaluationGroundedGenerator,
)


def _positive_rate(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("pricing rates must be greater than zero")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze Pliris evaluation contexts or explicitly run the Phase 6 prompt comparison."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--plan",
        action="store_true",
        help="Print the frozen plan without external calls.",
    )
    mode.add_argument(
        "--prepare-contexts",
        action="store_true",
        help=(
            "Run hosted retrieval once per retrieval case and "
            "freeze the contexts. This invokes embeddings."
        ),
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help=("Run generation comparisons from an existing frozen context file."),
    )
    parser.add_argument(
        "--refresh-contexts",
        action="store_true",
        help="Replace an existing frozen-context file.",
    )
    parser.add_argument(
        "--generation-input-price-per-million",
        type=_positive_rate,
    )
    parser.add_argument(
        "--generation-output-price-per-million",
        type=_positive_rate,
    )
    parser.add_argument(
        "--embedding-input-price-per-million",
        type=_positive_rate,
    )
    return parser


def _require(value: float | None, option: str) -> float:
    if value is None:
        raise SystemExit(f"{option} is required for this execution mode.")
    return value


async def _main() -> None:
    args = _parser().parse_args()
    repo_root = Path.cwd()
    contract = load_evaluation_contract(repo_root)
    output_root = deterministic_output_root(
        repo_root,
        contract,
    )
    context_path = output_root / contract.config.outputs.frozen_contexts_jsonl

    if args.plan:
        print("contract_fingerprint:", contract_fingerprint(contract))
        print("cases:", len(contract.benchmark.cases))
        print("variants:", len(contract.prompt_variants.variants))
        print("planned_attempts:", contract.primary_live_calls)
        print(
            "expected_generation_api_calls:",
            expected_generation_api_calls(contract),
        )
        print("frozen_context_path:", context_path)
        print("output_root:", output_root)
        print("external_calls: 0")
        return

    if args.prepare_contexts:
        embedding_rate = _require(
            args.embedding_input_price_per_million,
            "--embedding-input-price-per-million",
        )
        if context_path.exists() and not args.refresh_contexts:
            bundle = load_frozen_contexts(
                context_path,
                contract,
            )
            print(
                "Reused existing frozen contexts:",
                context_path,
            )
            print(
                "embedding_input_tokens:",
                bundle.manifest.embedding_input_tokens,
            )
            print("external_calls: 0")
            return

        estimated_embedding_tokens = sum(
            estimate_text_tokens(
                case.retrieval_query or case.question,
                contract.config.model,
            )
            for case in contract.benchmark.cases
            if case.context_strategy.value == "retrieval"
        )
        estimated_embedding_cost = estimated_embedding_tokens / 1_000_000 * embedding_rate
        if (
            estimated_embedding_tokens > contract.config.budget.max_total_input_tokens
            or estimated_embedding_cost > contract.config.budget.max_estimated_cost_usd
        ):
            raise SystemExit(
                "Estimated context-freezing cost exceeds the frozen evaluation budget."
            )

        from ingestion.embedding_service import EmbeddingService
        from pliris.retrieval.hosted_hybrid import (
            HostedHybridRetriever,
        )

        meter = MeteredEmbeddingService(EmbeddingService())
        retriever = HostedHybridRetriever(
            embedding_service=meter,
        )
        bundle = await freeze_contexts(
            contract,
            retriever=retriever,
            embedding_usage_provider=lambda: meter.input_tokens,
            embedding_price_per_million=embedding_rate,
        )
        write_frozen_contexts(
            context_path,
            bundle,
        )
        print("Frozen contexts:", context_path)
        print(
            "embedding_input_tokens:",
            bundle.manifest.embedding_input_tokens,
        )
        print(
            "embedding_estimated_cost_usd:",
            bundle.manifest.embedding_estimated_cost_usd,
        )
        for record in bundle.records:
            print(
                record.case_id,
                "strategy=",
                record.context_strategy.value,
                "sources=",
                len(record.sources),
                "page_overlap=",
                record.quality.page_overlap_count,
                "term_groups=",
                record.quality.matched_term_group_count,
                "passed=",
                record.quality.passed,
            )
        return

    generation_input_rate = _require(
        args.generation_input_price_per_million,
        "--generation-input-price-per-million",
    )
    generation_output_rate = _require(
        args.generation_output_price_per_million,
        "--generation-output-price-per-million",
    )
    bundle = load_frozen_contexts(
        context_path,
        contract,
    )
    generator = EvaluationGroundedGenerator(
        max_output_tokens=(contract.config.generation.max_output_tokens),
        reasoning_effort=(contract.config.generation.reasoning_effort),
        store=contract.config.generation.store,
    )
    summary = await run_primary_comparison(
        contract,
        bundle,
        generator=generator,
        pricing_rates=PricingRates(
            generation_input_per_million=(generation_input_rate),
            generation_output_per_million=(generation_output_rate),
        ),
        output_root=output_root,
    )
    print("complete:", summary["complete"])
    print(
        "recorded_attempts:",
        summary["recorded_attempts"],
    )
    print(
        "estimated_cost_usd:",
        summary["budget"]["estimated_cost_usd"],
    )
    print(
        "summary:",
        output_root / contract.config.outputs.automated_summary_md,
    )


if __name__ == "__main__":
    asyncio.run(_main())
