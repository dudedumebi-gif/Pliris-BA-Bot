from __future__ import annotations

import csv
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tiktoken
from pydantic import Field

from evaluation.llm_contexts import (
    FrozenContextBundle,
    FrozenContextRecord,
)
from evaluation.llm_contract import (
    EvaluationCase,
    EvaluationContract,
    PromptVariant,
    StrictModel,
    contract_fingerprint,
)
from evaluation.llm_scoring import (
    AutomatedEvaluation,
    score_answer,
)
from evaluation.llm_variant_generator import (
    VariantGenerationResult,
    instructions_for_variant,
    user_input_for_case,
)


class BudgetExceeded(RuntimeError):
    """Raised before a paid request would exceed a configured limit."""


class PricingRates(StrictModel):
    generation_input_per_million: float = Field(gt=0)
    generation_output_per_million: float = Field(gt=0)


class BudgetSnapshot(StrictModel):
    generation_api_calls: int = Field(ge=0)
    embedding_input_tokens: int = Field(ge=0)
    generation_input_tokens: int = Field(ge=0)
    generation_output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)


class BudgetLedger:
    def __init__(
        self,
        contract: EvaluationContract,
        rates: PricingRates,
        *,
        embedding_input_tokens: int = 0,
        embedding_cost_usd: float = 0.0,
        existing_generation_api_calls: int = 0,
        existing_generation_input_tokens: int = 0,
        existing_generation_output_tokens: int = 0,
        existing_generation_cost_usd: float = 0.0,
    ) -> None:
        self.contract = contract
        self.rates = rates
        self.generation_api_calls = existing_generation_api_calls
        self.embedding_input_tokens = embedding_input_tokens
        self.generation_input_tokens = existing_generation_input_tokens
        self.generation_output_tokens = existing_generation_output_tokens
        self.estimated_cost_usd = embedding_cost_usd + existing_generation_cost_usd

    def _generation_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        return (
            input_tokens / 1_000_000 * self.rates.generation_input_per_million
            + output_tokens / 1_000_000 * self.rates.generation_output_per_million
        )

    def preflight_generation(
        self,
        *,
        estimated_input_tokens: int,
        maximum_output_tokens: int,
    ) -> None:
        budget = self.contract.config.budget
        if self.generation_api_calls + 1 > budget.max_primary_live_calls:
            raise BudgetExceeded("Generation call budget would be exceeded.")

        projected_input = (
            self.embedding_input_tokens + self.generation_input_tokens + estimated_input_tokens
        )
        if projected_input > budget.max_total_input_tokens:
            raise BudgetExceeded("Input-token budget would be exceeded.")

        projected_output = self.generation_output_tokens + maximum_output_tokens
        if projected_output > budget.max_total_output_tokens:
            raise BudgetExceeded("Output-token budget would be exceeded.")

        projected_cost = self.estimated_cost_usd + self._generation_cost(
            estimated_input_tokens,
            maximum_output_tokens,
        )
        if projected_cost > budget.max_estimated_cost_usd:
            raise BudgetExceeded("Estimated cost ceiling would be exceeded.")

    def record_generation(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        fallback_input_tokens: int,
        fallback_output_tokens: int,
    ) -> tuple[int, int, float, bool]:
        resolved_input = input_tokens if input_tokens is not None else fallback_input_tokens
        resolved_output = output_tokens if output_tokens is not None else fallback_output_tokens
        estimated_usage = input_tokens is None or output_tokens is None
        call_cost = self._generation_cost(
            resolved_input,
            resolved_output,
        )

        self.generation_api_calls += 1
        self.generation_input_tokens += resolved_input
        self.generation_output_tokens += resolved_output
        self.estimated_cost_usd += call_cost

        return (
            resolved_input,
            resolved_output,
            round(call_cost, 8),
            estimated_usage,
        )

    def exceeded_after_recording(self) -> bool:
        budget = self.contract.config.budget
        return (
            self.generation_api_calls > budget.max_primary_live_calls
            or (
                self.embedding_input_tokens + self.generation_input_tokens
                > budget.max_total_input_tokens
            )
            or (self.generation_output_tokens > budget.max_total_output_tokens)
            or (self.estimated_cost_usd > budget.max_estimated_cost_usd)
        )

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            generation_api_calls=self.generation_api_calls,
            embedding_input_tokens=self.embedding_input_tokens,
            generation_input_tokens=self.generation_input_tokens,
            generation_output_tokens=self.generation_output_tokens,
            estimated_cost_usd=round(
                self.estimated_cost_usd,
                8,
            ),
        )


@dataclass(frozen=True, slots=True)
class RunPlanItem:
    case_id: str
    variant_id: str
    repetition: int

    @property
    def attempt_id(self) -> str:
        return f"{self.case_id}::{self.variant_id}::r{self.repetition}"


class RawRunRecord(StrictModel):
    record_type: str = "generation_result"
    contract_fingerprint: str = Field(min_length=64, max_length=64)
    attempt_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    request_mode: str = Field(min_length=1)
    context_fingerprint: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern=r"^(success|error)$")
    api_called: bool
    answer: str | None = None
    citation_ids: tuple[str, ...] = ()
    insufficient_evidence: bool | None = None
    model: str | None = None
    response_id: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_input_tokens: int = Field(ge=0)
    recorded_input_tokens: int = Field(ge=0)
    recorded_output_tokens: int = Field(ge=0)
    call_estimated_cost_usd: float = Field(ge=0)
    usage_estimated: bool
    latency_ms: float = Field(ge=0)
    raw_output_text: str | None = None
    automated_evaluation: AutomatedEvaluation | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at_utc: str = Field(min_length=1)


def estimate_text_tokens(
    text: str,
    model: str,
) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))


def estimate_generation_input_tokens(
    *,
    instructions: str,
    user_input: str,
    model: str,
) -> int:
    return estimate_text_tokens(instructions, model) + estimate_text_tokens(user_input, model) + 32


def expected_generation_api_calls(
    contract: EvaluationContract,
) -> int:
    non_empty_cases = sum(
        case.context_strategy.value != "empty" for case in contract.benchmark.cases
    )
    return non_empty_cases * len(contract.config.variant_ids) * contract.config.primary_repetitions


def build_run_plan(
    contract: EvaluationContract,
) -> tuple[RunPlanItem, ...]:
    variants = list(contract.config.variant_ids)
    plan: list[RunPlanItem] = []

    for repetition in range(
        1,
        contract.config.primary_repetitions + 1,
    ):
        for case_index, case in enumerate(contract.benchmark.cases):
            rotation = (case_index + repetition - 1) % len(variants)
            ordered = variants[rotation:] + variants[:rotation]
            plan.extend(
                RunPlanItem(
                    case_id=case.id,
                    variant_id=variant_id,
                    repetition=repetition,
                )
                for variant_id in ordered
            )
    return tuple(plan)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())


def load_all_records(
    path: Path,
    fingerprint: str,
) -> tuple[RawRunRecord, ...]:
    if not path.exists():
        return ()

    records: list[RawRunRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = RawRunRecord.model_validate_json(line)
        if record.contract_fingerprint == fingerprint:
            records.append(record)
    return tuple(records)


def load_latest_records(
    path: Path,
    fingerprint: str,
) -> dict[str, RawRunRecord]:
    latest: dict[str, RawRunRecord] = {}
    for record in load_all_records(path, fingerprint):
        latest[record.attempt_id] = record
    return latest


def _record_success(
    *,
    fingerprint: str,
    plan_item: RunPlanItem,
    case: EvaluationCase,
    variant: PromptVariant,
    context_record: FrozenContextRecord,
    result: VariantGenerationResult,
    estimated_input_tokens: int,
    recorded_input_tokens: int,
    recorded_output_tokens: int,
    call_cost: float,
    usage_estimated: bool,
    latency_ms: float,
    automated_evaluation: AutomatedEvaluation,
) -> RawRunRecord:
    usage = result.answer.usage
    return RawRunRecord(
        contract_fingerprint=fingerprint,
        attempt_id=plan_item.attempt_id,
        case_id=case.id,
        variant_id=variant.id,
        repetition=plan_item.repetition,
        request_mode=case.request_mode.value,
        context_fingerprint=context_record.context_fingerprint,
        status="success",
        api_called=result.api_called,
        answer=result.answer.answer,
        citation_ids=result.answer.citation_ids,
        insufficient_evidence=(result.answer.insufficient_evidence),
        model=result.answer.model,
        response_id=result.answer.response_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        total_tokens=usage.total_tokens,
        estimated_input_tokens=estimated_input_tokens,
        recorded_input_tokens=recorded_input_tokens,
        recorded_output_tokens=recorded_output_tokens,
        call_estimated_cost_usd=call_cost,
        usage_estimated=usage_estimated,
        latency_ms=latency_ms,
        raw_output_text=result.raw_output_text,
        automated_evaluation=automated_evaluation,
        created_at_utc=datetime.now(UTC).isoformat(),
    )


def _record_error(
    *,
    fingerprint: str,
    plan_item: RunPlanItem,
    case: EvaluationCase,
    variant: PromptVariant,
    context_record: FrozenContextRecord,
    api_called: bool,
    estimated_input_tokens: int,
    recorded_input_tokens: int,
    recorded_output_tokens: int,
    call_cost: float,
    latency_ms: float,
    exc: Exception,
) -> RawRunRecord:
    return RawRunRecord(
        contract_fingerprint=fingerprint,
        attempt_id=plan_item.attempt_id,
        case_id=case.id,
        variant_id=variant.id,
        repetition=plan_item.repetition,
        request_mode=case.request_mode.value,
        context_fingerprint=context_record.context_fingerprint,
        status="error",
        api_called=api_called,
        estimated_input_tokens=estimated_input_tokens,
        recorded_input_tokens=recorded_input_tokens,
        recorded_output_tokens=recorded_output_tokens,
        call_estimated_cost_usd=call_cost,
        usage_estimated=api_called,
        latency_ms=latency_ms,
        error_type=type(exc).__name__,
        error_message=str(exc),
        created_at_utc=datetime.now(UTC).isoformat(),
    )


def _dimension_names() -> tuple[str, ...]:
    return (
        "groundedness",
        "citation_quality",
        "mode_fulfillment",
        "completeness",
        "relevance_clarity",
        "uncertainty_handling",
    )


def aggregate_records(
    contract: EvaluationContract,
    records: dict[str, RawRunRecord],
    budget: BudgetSnapshot,
) -> dict[str, Any]:
    plan = build_run_plan(contract)
    by_variant: dict[str, list[RawRunRecord]] = defaultdict(list)
    for record in records.values():
        by_variant[record.variant_id].append(record)

    variant_summaries: list[dict[str, Any]] = []
    for variant_id in sorted(contract.config.variant_ids):
        variant_records = by_variant.get(variant_id, [])
        successes = [
            record
            for record in variant_records
            if record.status == "success" and record.automated_evaluation is not None
        ]
        errors = [record for record in variant_records if record.status == "error"]
        critical_count = sum(
            bool(record.automated_evaluation and record.automated_evaluation.critical_failures)
            for record in successes
        )
        dimension_means = {}
        for name in _dimension_names():
            values = [
                float(
                    getattr(
                        record.automated_evaluation,
                        name,
                    )
                )
                for record in successes
                if record.automated_evaluation is not None
            ]
            dimension_means[name] = round(sum(values) / len(values), 4) if values else None

        weighted_scores = [
            record.automated_evaluation.weighted_score
            for record in successes
            if record.automated_evaluation is not None
        ]
        passed_count = sum(
            bool(record.automated_evaluation and record.automated_evaluation.passed)
            for record in successes
        )
        variant_summaries.append(
            {
                "variant_id": variant_id,
                "attempts_recorded": len(variant_records),
                "successes": len(successes),
                "errors": len(errors),
                "automated_pass_rate": (
                    round(passed_count / len(successes), 4) if successes else None
                ),
                "critical_failure_rate": (
                    round(critical_count / len(successes), 4) if successes else None
                ),
                "mean_weighted_score": (
                    round(
                        sum(weighted_scores) / len(weighted_scores),
                        4,
                    )
                    if weighted_scores
                    else None
                ),
                "mean_latency_ms": (
                    round(
                        sum(record.latency_ms for record in successes) / len(successes),
                        2,
                    )
                    if successes
                    else None
                ),
                "input_tokens": sum(record.recorded_input_tokens for record in variant_records),
                "output_tokens": sum(record.recorded_output_tokens for record in variant_records),
                "estimated_cost_usd": round(
                    sum(record.call_estimated_cost_usd for record in variant_records),
                    8,
                ),
                "dimension_means": dimension_means,
            }
        )

    planned_ids = {item.attempt_id for item in plan}
    recorded_ids = set(records)
    return {
        "contract_fingerprint": contract_fingerprint(contract),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "selection_status": ("not_performed_phase_6_step_2"),
        "planned_attempts": len(plan),
        "recorded_attempts": len(planned_ids & recorded_ids),
        "complete": planned_ids <= recorded_ids,
        "expected_generation_api_calls": (expected_generation_api_calls(contract)),
        "budget": budget.model_dump(mode="json"),
        "variants": variant_summaries,
    }


def write_automated_scores_csv(
    path: Path,
    records: dict[str, RawRunRecord],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "attempt_id",
        "case_id",
        "variant_id",
        "repetition",
        "request_mode",
        "status",
        "api_called",
        "weighted_score",
        "passed",
        "critical_failures",
        *_dimension_names(),
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "error_type",
        "error_message",
    ]
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        for record in sorted(
            records.values(),
            key=lambda item: item.attempt_id,
        ):
            evaluation = record.automated_evaluation
            row = {
                "attempt_id": record.attempt_id,
                "case_id": record.case_id,
                "variant_id": record.variant_id,
                "repetition": record.repetition,
                "request_mode": record.request_mode,
                "status": record.status,
                "api_called": record.api_called,
                "weighted_score": (evaluation.weighted_score if evaluation else ""),
                "passed": (evaluation.passed if evaluation else ""),
                "critical_failures": ("|".join(evaluation.critical_failures) if evaluation else ""),
                "latency_ms": record.latency_ms,
                "input_tokens": record.recorded_input_tokens,
                "output_tokens": record.recorded_output_tokens,
                "estimated_cost_usd": (record.call_estimated_cost_usd),
                "error_type": record.error_type or "",
                "error_message": record.error_message or "",
            }
            for name in _dimension_names():
                row[name] = getattr(evaluation, name) if evaluation else ""
            writer.writerow(row)


def write_summary_reports(
    *,
    json_path: Path,
    markdown_path: Path,
    summary: dict[str, Any],
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Pliris Prompt Comparison — Automated Summary",
        "",
        "> Phase 6 Step 2 does not select a production prompt.",
        "",
        f"- Complete: `{summary['complete']}`",
        (f"- Attempts: `{summary['recorded_attempts']}/{summary['planned_attempts']}`"),
        (f"- Expected generation API calls: `{summary['expected_generation_api_calls']}`"),
        (f"- Estimated total cost: `${summary['budget']['estimated_cost_usd']:.8f}`"),
        "",
        "## Variant results",
        "",
        ("| Variant | Successes | Errors | Mean score | Pass rate | Critical failure rate |"),
        "|---|---:|---:|---:|---:|---:|",
    ]
    for variant in summary["variants"]:
        lines.append(
            "| "
            f"{variant['variant_id']} | "
            f"{variant['successes']} | "
            f"{variant['errors']} | "
            f"{variant['mean_weighted_score']} | "
            f"{variant['automated_pass_rate']} | "
            f"{variant['critical_failure_rate']} |"
        )

    lines.extend(
        [
            "",
            "Automated scores are deterministic structural checks. "
            "They do not replace the blinded semantic review in Step 3.",
            "",
        ]
    )
    markdown_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


async def run_primary_comparison(
    contract: EvaluationContract,
    bundle: FrozenContextBundle,
    *,
    generator: Any,
    pricing_rates: PricingRates,
    output_root: Path,
) -> dict[str, Any]:
    fingerprint = contract_fingerprint(contract)
    if bundle.manifest.contract_fingerprint != fingerprint:
        raise ValueError("Frozen contexts do not match the active contract.")

    contexts = bundle.by_case_id()
    cases = {case.id: case for case in contract.benchmark.cases}
    variants = {variant.id: variant for variant in contract.prompt_variants.variants}

    raw_path = output_root / contract.config.outputs.raw_outputs_jsonl
    all_existing = load_all_records(
        raw_path,
        fingerprint,
    )
    latest = load_latest_records(
        raw_path,
        fingerprint,
    )
    paid_existing = [record for record in all_existing if record.api_called]
    ledger = BudgetLedger(
        contract,
        pricing_rates,
        embedding_input_tokens=(bundle.manifest.embedding_input_tokens),
        embedding_cost_usd=(bundle.manifest.embedding_estimated_cost_usd),
        existing_generation_api_calls=len(paid_existing),
        existing_generation_input_tokens=sum(
            record.recorded_input_tokens for record in paid_existing
        ),
        existing_generation_output_tokens=sum(
            record.recorded_output_tokens for record in paid_existing
        ),
        existing_generation_cost_usd=sum(
            record.call_estimated_cost_usd for record in paid_existing
        ),
    )
    stopped_for_budget = False

    for plan_item in build_run_plan(contract):
        existing = latest.get(plan_item.attempt_id)
        if existing is not None and existing.status == "success":
            continue

        case = cases[plan_item.case_id]
        variant = variants[plan_item.variant_id]
        context_record = contexts[case.id]
        context = context_record.to_assembled_context()
        instructions = instructions_for_variant(
            case.request_mode.value,
            variant,
        )
        user_input = user_input_for_case(
            case.question,
            context,
        )
        estimated_input = estimate_generation_input_tokens(
            instructions=instructions,
            user_input=user_input,
            model=contract.config.model,
        )
        api_expected = bool(context.sources)

        if api_expected:
            try:
                ledger.preflight_generation(
                    estimated_input_tokens=estimated_input,
                    maximum_output_tokens=(contract.config.generation.max_output_tokens),
                )
            except BudgetExceeded:
                stopped_for_budget = True
                break

        started = time.perf_counter()
        try:
            result = await generator.generate_variant(
                question=case.question,
                context=context,
                request_mode=case.request_mode.value,
                variant=variant,
                model=contract.config.model,
            )
        except Exception as exc:
            latency_ms = round(
                (time.perf_counter() - started) * 1_000,
                3,
            )
            if api_expected:
                (
                    recorded_input,
                    recorded_output,
                    call_cost,
                    _,
                ) = ledger.record_generation(
                    input_tokens=None,
                    output_tokens=None,
                    fallback_input_tokens=estimated_input,
                    fallback_output_tokens=(contract.config.generation.max_output_tokens),
                )
            else:
                recorded_input = 0
                recorded_output = 0
                call_cost = 0.0

            record = _record_error(
                fingerprint=fingerprint,
                plan_item=plan_item,
                case=case,
                variant=variant,
                context_record=context_record,
                api_called=api_expected,
                estimated_input_tokens=estimated_input,
                recorded_input_tokens=recorded_input,
                recorded_output_tokens=recorded_output,
                call_cost=call_cost,
                latency_ms=latency_ms,
                exc=exc,
            )
        else:
            latency_ms = round(
                (time.perf_counter() - started) * 1_000,
                3,
            )
            if result.api_called:
                (
                    recorded_input,
                    recorded_output,
                    call_cost,
                    usage_estimated,
                ) = ledger.record_generation(
                    input_tokens=(result.answer.usage.input_tokens),
                    output_tokens=(result.answer.usage.output_tokens),
                    fallback_input_tokens=estimated_input,
                    fallback_output_tokens=(contract.config.generation.max_output_tokens),
                )
            else:
                recorded_input = 0
                recorded_output = 0
                call_cost = 0.0
                usage_estimated = False

            automated = score_answer(
                case,
                result.answer,
                dimensions=contract.config.scoring_dimensions,
                pass_threshold=(contract.config.thresholds.automated_weighted_score_min),
            )
            record = _record_success(
                fingerprint=fingerprint,
                plan_item=plan_item,
                case=case,
                variant=variant,
                context_record=context_record,
                result=result,
                estimated_input_tokens=estimated_input,
                recorded_input_tokens=recorded_input,
                recorded_output_tokens=recorded_output,
                call_cost=call_cost,
                usage_estimated=usage_estimated,
                latency_ms=latency_ms,
                automated_evaluation=automated,
            )

        _append_jsonl(
            raw_path,
            record.model_dump(mode="json"),
        )
        latest[record.attempt_id] = record
        if ledger.exceeded_after_recording():
            stopped_for_budget = True
            break

    current = load_latest_records(raw_path, fingerprint)
    summary = aggregate_records(
        contract,
        current,
        ledger.snapshot(),
    )
    summary["stopped_for_budget"] = stopped_for_budget
    write_automated_scores_csv(
        output_root / contract.config.outputs.automated_scores_csv,
        current,
    )
    write_summary_reports(
        json_path=(output_root / contract.config.outputs.automated_summary_json),
        markdown_path=(output_root / contract.config.outputs.automated_summary_md),
        summary=summary,
    )
    return summary
