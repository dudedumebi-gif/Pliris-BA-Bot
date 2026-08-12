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

from evaluation.llm_contexts import FrozenContextBundle, FrozenContextRecord
from evaluation.llm_contract import (
    EvaluationCase,
    EvaluationContract,
    PromptVariant,
    contract_fingerprint,
)
from evaluation.llm_finalist_contract import (
    FinalistConfirmationContract,
    finalist_contract_fingerprint,
)
from evaluation.llm_runner import (
    PricingRates,
    RawRunRecord,
    estimate_generation_input_tokens,
    load_all_records,
    load_latest_records,
)
from evaluation.llm_scoring import AutomatedEvaluation, score_answer
from evaluation.llm_variant_generator import (
    VariantGenerationResult,
    instructions_for_variant,
    user_input_for_case,
)


class FinalistBudgetExceeded(RuntimeError):
    """Raised before a finalist request would exceed the frozen total budget."""


@dataclass(frozen=True, slots=True)
class FinalistPlanItem:
    case_id: str
    variant_id: str
    repetition: int

    @property
    def attempt_id(self) -> str:
        return f"{self.case_id}::{self.variant_id}::confirmation-r{self.repetition}"


class FinalistBudgetLedger:
    def __init__(
        self,
        parent: EvaluationContract,
        rates: PricingRates,
        *,
        generation_api_calls: int,
        embedding_input_tokens: int,
        generation_input_tokens: int,
        generation_output_tokens: int,
        estimated_cost_usd: float,
    ) -> None:
        self.parent = parent
        self.rates = rates
        self.generation_api_calls = generation_api_calls
        self.embedding_input_tokens = embedding_input_tokens
        self.generation_input_tokens = generation_input_tokens
        self.generation_output_tokens = generation_output_tokens
        self.estimated_cost_usd = estimated_cost_usd

    def _cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.rates.generation_input_per_million
            + output_tokens / 1_000_000 * self.rates.generation_output_per_million
        )

    def preflight(self, *, estimated_input_tokens: int, maximum_output_tokens: int) -> None:
        budget = self.parent.config.budget
        if self.generation_api_calls + 1 > budget.max_total_live_calls:
            raise FinalistBudgetExceeded("Total live-call budget would be exceeded.")
        if (
            self.embedding_input_tokens + self.generation_input_tokens + estimated_input_tokens
            > budget.max_total_input_tokens
        ):
            raise FinalistBudgetExceeded("Total input-token budget would be exceeded.")
        if self.generation_output_tokens + maximum_output_tokens > budget.max_total_output_tokens:
            raise FinalistBudgetExceeded("Total output-token budget would be exceeded.")
        if (
            self.estimated_cost_usd + self._cost(estimated_input_tokens, maximum_output_tokens)
            > budget.max_estimated_cost_usd
        ):
            raise FinalistBudgetExceeded("Total estimated-cost ceiling would be exceeded.")

    def record(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        fallback_input_tokens: int,
        fallback_output_tokens: int,
    ) -> tuple[int, int, float, bool]:
        resolved_input = input_tokens if input_tokens is not None else fallback_input_tokens
        resolved_output = output_tokens if output_tokens is not None else fallback_output_tokens
        usage_estimated = input_tokens is None or output_tokens is None
        call_cost = self._cost(resolved_input, resolved_output)
        self.generation_api_calls += 1
        self.generation_input_tokens += resolved_input
        self.generation_output_tokens += resolved_output
        self.estimated_cost_usd += call_cost
        return resolved_input, resolved_output, round(call_cost, 8), usage_estimated

    def snapshot(self) -> dict[str, int | float]:
        return {
            "generation_api_calls": self.generation_api_calls,
            "embedding_input_tokens": self.embedding_input_tokens,
            "generation_input_tokens": self.generation_input_tokens,
            "generation_output_tokens": self.generation_output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 8),
        }


def build_finalist_plan(
    parent: EvaluationContract,
    confirmation: FinalistConfirmationContract,
) -> tuple[FinalistPlanItem, ...]:
    variants = list(confirmation.finalist_ids)
    plan: list[FinalistPlanItem] = []
    for repetition in range(1, confirmation.repetitions + 1):
        for case_index, case in enumerate(parent.benchmark.cases):
            rotation = (case_index + repetition - 1) % len(variants)
            ordered = variants[rotation:] + variants[:rotation]
            plan.extend(
                FinalistPlanItem(
                    case_id=case.id,
                    variant_id=variant_id,
                    repetition=repetition,
                )
                for variant_id in ordered
            )
    return tuple(plan)


def expected_finalist_api_calls(
    parent: EvaluationContract,
    confirmation: FinalistConfirmationContract,
) -> int:
    non_empty = sum(case.context_strategy.value != "empty" for case in parent.benchmark.cases)
    return non_empty * len(confirmation.variants) * confirmation.repetitions


def validate_source_human_evidence(
    repo_root: Path,
    parent: EvaluationContract,
    confirmation: FinalistConfirmationContract,
) -> dict[str, Any]:
    path = repo_root.resolve() / confirmation.source_human_summary_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Step 3 human summary not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Step 3 human summary is invalid JSON: {path}") from exc

    if payload.get("contract_fingerprint") != contract_fingerprint(parent):
        raise ValueError("Step 3 human summary does not match the parent contract")
    if payload.get("review_set_fingerprint") != confirmation.source_human_review_fingerprint:
        raise ValueError("Step 3 human-review fingerprint does not match the finalist contract")
    if payload.get("selection_status") != "not_performed_phase_6_step_3":
        raise ValueError("Step 3 summary must not contain a prompt selection")
    if payload.get("attempts_reviewed") != parent.primary_live_calls:
        raise ValueError("Step 3 summary does not contain every primary attempt")

    variants = payload.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("Step 3 summary is missing variant results")
    by_id = {item.get("variant_id"): item for item in variants if isinstance(item, dict)}
    expected_ids = set(parent.config.variant_ids)
    if set(by_id) != expected_ids:
        raise ValueError("Step 3 summary variants do not match the frozen comparison")
    leader = max(
        by_id.values(),
        key=lambda item: float(item.get("mean_weighted_score", -1)),
    )
    if leader.get("variant_id") != confirmation.source_candidate_id:
        raise ValueError("configured source candidate is not the leading human-scored variant")
    if any(bool(item.get("human_threshold_gate_met")) for item in by_id.values()):
        raise ValueError("a frozen variant unexpectedly passed the Step 3 acceptance gate")
    return payload


def validate_primary_evidence(
    parent: EvaluationContract,
    raw_path: Path,
) -> tuple[RawRunRecord, ...]:
    fingerprint = contract_fingerprint(parent)
    records = load_all_records(raw_path, fingerprint)
    latest = load_latest_records(raw_path, fingerprint)
    planned = {item.attempt_id for item in _primary_plan(parent)}
    if not records or not planned <= set(latest):
        raise ValueError("the original primary comparison is incomplete")
    return records


def _primary_plan(parent: EvaluationContract) -> tuple[Any, ...]:
    from evaluation.llm_runner import build_run_plan

    return build_run_plan(parent)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _success_record(
    *,
    fingerprint: str,
    item: FinalistPlanItem,
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
    automated: AutomatedEvaluation,
) -> RawRunRecord:
    usage = result.answer.usage
    return RawRunRecord(
        contract_fingerprint=fingerprint,
        attempt_id=item.attempt_id,
        case_id=case.id,
        variant_id=variant.id,
        repetition=item.repetition,
        request_mode=case.request_mode.value,
        context_fingerprint=context_record.context_fingerprint,
        status="success",
        api_called=result.api_called,
        answer=result.answer.answer,
        citation_ids=result.answer.citation_ids,
        insufficient_evidence=result.answer.insufficient_evidence,
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
        automated_evaluation=automated,
        created_at_utc=datetime.now(UTC).isoformat(),
    )


def _error_record(
    *,
    fingerprint: str,
    item: FinalistPlanItem,
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
        attempt_id=item.attempt_id,
        case_id=case.id,
        variant_id=variant.id,
        repetition=item.repetition,
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


def aggregate_finalist_records(
    parent: EvaluationContract,
    confirmation: FinalistConfirmationContract,
    records: dict[str, RawRunRecord],
    budget: dict[str, int | float],
) -> dict[str, Any]:
    plan = build_finalist_plan(parent, confirmation)
    planned_ids = {item.attempt_id for item in plan}
    by_variant: dict[str, list[RawRunRecord]] = defaultdict(list)
    for attempt_id, record in records.items():
        if attempt_id in planned_ids:
            by_variant[record.variant_id].append(record)

    attempts_per_variant = len(parent.benchmark.cases) * confirmation.repetitions
    variant_summaries: list[dict[str, Any]] = []
    for variant_id in sorted(confirmation.finalist_ids):
        variant_records = by_variant.get(variant_id, [])
        successes = [
            record
            for record in variant_records
            if record.status == "success" and record.automated_evaluation is not None
        ]
        errors = [record for record in variant_records if record.status == "error"]
        critical_successes = sum(
            bool(record.automated_evaluation and record.automated_evaluation.critical_failures)
            for record in successes
        )
        critical_count = len(errors) + critical_successes
        weighted = [
            record.automated_evaluation.weighted_score
            for record in successes
            if record.automated_evaluation is not None
        ] + [0.0] * len(errors)
        mean_score = round(sum(weighted) / len(variant_records), 4) if variant_records else None
        passed_count = sum(
            bool(record.automated_evaluation and record.automated_evaluation.passed)
            for record in successes
        )
        critical_rate = round(critical_count / len(variant_records), 4) if variant_records else None
        complete = len(variant_records) == attempts_per_variant
        gate = bool(
            complete
            and len(errors) <= confirmation.selection_policy.response_contract_failure_max
            and critical_rate is not None
            and critical_rate <= confirmation.selection_policy.critical_failure_rate_max
            and mean_score is not None
            and mean_score >= confirmation.selection_policy.automated_weighted_score_min
        )
        variant_summaries.append(
            {
                "variant_id": variant_id,
                "attempts_recorded": len(variant_records),
                "successes": len(successes),
                "response_contract_failures": len(errors),
                "critical_failures": critical_count,
                "critical_failure_rate": critical_rate,
                "mean_weighted_score": mean_score,
                "automated_pass_rate": (
                    round(passed_count / len(variant_records), 4) if variant_records else None
                ),
                "automated_gate_met": gate,
                "estimated_cost_usd": round(
                    sum(record.call_estimated_cost_usd for record in variant_records), 8
                ),
            }
        )

    recorded_ids = set(records) & planned_ids
    complete = planned_ids <= recorded_ids
    return {
        "parent_contract_fingerprint": contract_fingerprint(parent),
        "finalist_contract_fingerprint": finalist_contract_fingerprint(confirmation),
        "source_human_review_fingerprint": confirmation.source_human_review_fingerprint,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "planned_attempts": len(plan),
        "recorded_attempts": len(recorded_ids),
        "expected_generation_api_calls": expected_finalist_api_calls(parent, confirmation),
        "complete": complete,
        "selection_status": (
            "pending_blinded_human_review" if complete else "confirmation_incomplete"
        ),
        "budget": budget,
        "variants": variant_summaries,
    }


def _write_scores(path: Path, records: dict[str, RawRunRecord]) -> None:
    fields = [
        "attempt_id",
        "case_id",
        "variant_id",
        "status",
        "api_called",
        "weighted_score",
        "passed",
        "critical_failures",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "error_type",
        "error_message",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in sorted(records.values(), key=lambda value: value.attempt_id):
            evaluation = record.automated_evaluation
            writer.writerow(
                {
                    "attempt_id": record.attempt_id,
                    "case_id": record.case_id,
                    "variant_id": record.variant_id,
                    "status": record.status,
                    "api_called": record.api_called,
                    "weighted_score": evaluation.weighted_score if evaluation else "",
                    "passed": evaluation.passed if evaluation else "",
                    "critical_failures": (
                        "|".join(evaluation.critical_failures) if evaluation else ""
                    ),
                    "latency_ms": record.latency_ms,
                    "input_tokens": record.recorded_input_tokens,
                    "output_tokens": record.recorded_output_tokens,
                    "estimated_cost_usd": record.call_estimated_cost_usd,
                    "error_type": record.error_type or "",
                    "error_message": record.error_message or "",
                }
            )


def _write_summary(json_path: Path, md_path: Path, summary: dict[str, Any]) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Pliris Finalist Confirmation — Automated Summary",
        "",
        "> This confirmation does not select or change the production prompt.",
        "",
        f"- Complete: `{summary['complete']}`",
        f"- Attempts: `{summary['recorded_attempts']}/{summary['planned_attempts']}`",
        f"- Expected generation API calls: `{summary['expected_generation_api_calls']}`",
        f"- Total estimated evaluation cost: `${summary['budget']['estimated_cost_usd']:.8f}`",
        f"- Selection status: `{summary['selection_status']}`",
        "",
        (
            "| Finalist | Successes | Contract failures | Critical rate | "
            "Mean score | Pass rate | Automated gate |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in summary["variants"]:
        lines.append(
            "| "
            f"{variant['variant_id']} | "
            f"{variant['successes']} | "
            f"{variant['response_contract_failures']} | "
            f"{variant['critical_failure_rate']} | "
            f"{variant['mean_weighted_score']} | "
            f"{variant['automated_pass_rate']} | "
            f"{variant['automated_gate_met']} |"
        )
    lines.extend(
        [
            "",
            "A finalist must still pass blinded human review before Step 4 can select it.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")


async def run_finalist_confirmation(
    parent: EvaluationContract,
    confirmation: FinalistConfirmationContract,
    bundle: FrozenContextBundle,
    *,
    generator: Any,
    pricing_rates: PricingRates,
    repo_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    parent_fingerprint = contract_fingerprint(parent)
    if bundle.manifest.contract_fingerprint != parent_fingerprint:
        raise ValueError("frozen contexts do not match the parent evaluation contract")
    validate_source_human_evidence(repo_root, parent, confirmation)

    parent_output = repo_root.resolve() / parent.config.outputs.root
    primary_raw = parent_output / parent.config.outputs.raw_outputs_jsonl
    primary_records = validate_primary_evidence(parent, primary_raw)
    confirmation_fingerprint = finalist_contract_fingerprint(confirmation)
    raw_path = output_root / confirmation.outputs.raw_outputs_jsonl
    existing_all = load_all_records(raw_path, confirmation_fingerprint)
    existing = load_latest_records(raw_path, confirmation_fingerprint)

    paid_primary = [record for record in primary_records if record.api_called]
    paid_confirmation = [record for record in existing_all if record.api_called]
    ledger = FinalistBudgetLedger(
        parent,
        pricing_rates,
        generation_api_calls=len(paid_primary) + len(paid_confirmation),
        embedding_input_tokens=bundle.manifest.embedding_input_tokens,
        generation_input_tokens=sum(
            record.recorded_input_tokens for record in paid_primary + paid_confirmation
        ),
        generation_output_tokens=sum(
            record.recorded_output_tokens for record in paid_primary + paid_confirmation
        ),
        estimated_cost_usd=(
            bundle.manifest.embedding_estimated_cost_usd
            + sum(record.call_estimated_cost_usd for record in paid_primary + paid_confirmation)
        ),
    )

    contexts = bundle.by_case_id()
    cases = {case.id: case for case in parent.benchmark.cases}
    variants = {variant.id: variant for variant in confirmation.variants}
    stopped_for_budget = False

    for item in build_finalist_plan(parent, confirmation):
        if item.attempt_id in existing:
            continue
        case = cases[item.case_id]
        variant = variants[item.variant_id]
        context_record = contexts[case.id]
        context = context_record.to_assembled_context()
        estimated_input = estimate_generation_input_tokens(
            instructions=instructions_for_variant(case.request_mode.value, variant),
            user_input=user_input_for_case(case.question, context),
            model=parent.config.model,
        )
        api_expected = bool(context.sources)
        if api_expected:
            try:
                ledger.preflight(
                    estimated_input_tokens=estimated_input,
                    maximum_output_tokens=parent.config.generation.max_output_tokens,
                )
            except FinalistBudgetExceeded:
                stopped_for_budget = True
                break

        started = time.perf_counter()
        try:
            result = await generator.generate_variant(
                question=case.question,
                context=context,
                request_mode=case.request_mode.value,
                variant=variant,
                model=parent.config.model,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1_000, 3)
            if api_expected:
                recorded_input, recorded_output, cost, _ = ledger.record(
                    input_tokens=None,
                    output_tokens=None,
                    fallback_input_tokens=estimated_input,
                    fallback_output_tokens=parent.config.generation.max_output_tokens,
                )
            else:
                recorded_input, recorded_output, cost = 0, 0, 0.0
            record = _error_record(
                fingerprint=confirmation_fingerprint,
                item=item,
                case=case,
                variant=variant,
                context_record=context_record,
                api_called=api_expected,
                estimated_input_tokens=estimated_input,
                recorded_input_tokens=recorded_input,
                recorded_output_tokens=recorded_output,
                call_cost=cost,
                latency_ms=latency_ms,
                exc=exc,
            )
        else:
            latency_ms = round((time.perf_counter() - started) * 1_000, 3)
            if result.api_called:
                recorded_input, recorded_output, cost, usage_estimated = ledger.record(
                    input_tokens=result.answer.usage.input_tokens,
                    output_tokens=result.answer.usage.output_tokens,
                    fallback_input_tokens=estimated_input,
                    fallback_output_tokens=parent.config.generation.max_output_tokens,
                )
            else:
                recorded_input, recorded_output, cost, usage_estimated = 0, 0, 0.0, False
            automated = score_answer(
                case,
                result.answer,
                dimensions=parent.config.scoring_dimensions,
                pass_threshold=confirmation.selection_policy.automated_weighted_score_min,
            )
            record = _success_record(
                fingerprint=confirmation_fingerprint,
                item=item,
                case=case,
                variant=variant,
                context_record=context_record,
                result=result,
                estimated_input_tokens=estimated_input,
                recorded_input_tokens=recorded_input,
                recorded_output_tokens=recorded_output,
                call_cost=cost,
                usage_estimated=usage_estimated,
                latency_ms=latency_ms,
                automated=automated,
            )
        _append_jsonl(raw_path, record.model_dump(mode="json"))
        existing[record.attempt_id] = record

    current = load_latest_records(raw_path, confirmation_fingerprint)
    summary = aggregate_finalist_records(
        parent,
        confirmation,
        current,
        ledger.snapshot(),
    )
    summary["stopped_for_budget"] = stopped_for_budget
    _write_scores(output_root / confirmation.outputs.automated_scores_csv, current)
    _write_summary(
        output_root / confirmation.outputs.automated_summary_json,
        output_root / confirmation.outputs.automated_summary_md,
        summary,
    )
    return summary
