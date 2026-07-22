from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.llm_contract import load_evaluation_contract
from evaluation.llm_finalist_contract import (
    finalist_contract_fingerprint,
    load_finalist_confirmation_contract,
)
from evaluation.llm_finalist_runner import (
    FinalistBudgetExceeded,
    FinalistBudgetLedger,
    aggregate_finalist_records,
    build_finalist_plan,
    expected_finalist_api_calls,
    validate_source_human_evidence,
)
from evaluation.llm_runner import PricingRates, RawRunRecord
from evaluation.llm_scoring import AutomatedEvaluation

REPO_ROOT = Path(__file__).resolve().parents[2]


def contracts():
    parent = load_evaluation_contract(REPO_ROOT)
    confirmation = load_finalist_confirmation_contract(REPO_ROOT, parent)
    return parent, confirmation


def record(item, *, status="success", score=4.0, critical=()):
    evaluation = None
    if status == "success":
        evaluation = AutomatedEvaluation(
            groundedness=score,
            citation_quality=score,
            mode_fulfillment=score,
            completeness=score,
            relevance_clarity=score,
            uncertainty_handling=score,
            weighted_score=score,
            critical_failures=critical,
            passed=score >= 3.2 and not critical,
        )
    return RawRunRecord(
        contract_fingerprint="a" * 64,
        attempt_id=item.attempt_id,
        case_id=item.case_id,
        variant_id=item.variant_id,
        repetition=item.repetition,
        request_mode="grounded_question",
        context_fingerprint="b" * 64,
        status=status,
        api_called=True,
        answer="Supported [S1]." if status == "success" else None,
        citation_ids=("S1",) if status == "success" else (),
        insufficient_evidence=False if status == "success" else None,
        estimated_input_tokens=10,
        recorded_input_tokens=10,
        recorded_output_tokens=5,
        call_estimated_cost_usd=0.001,
        usage_estimated=False,
        latency_ms=1.0,
        automated_evaluation=evaluation,
        error_type="Error" if status == "error" else None,
        error_message="failed" if status == "error" else None,
        created_at_utc="2026-07-22T00:00:00+00:00",
    )


def test_contract_loads_against_frozen_parent() -> None:
    _parent, confirmation = contracts()
    assert confirmation.parent_contract_fingerprint
    assert confirmation.parent_contract_fingerprint == (
        "74c123e1b442a33c3628f0ad5207fc12fe3687847225f8a4962db571761fe271"
    )
    assert len(finalist_contract_fingerprint(confirmation)) == 64


def test_exactly_two_finalists_are_frozen() -> None:
    _, confirmation = contracts()
    assert confirmation.finalist_ids == (
        "production_baseline_v1",
        "decision_ready_hardened_v1",
    )


def test_control_is_unchanged_baseline() -> None:
    parent, confirmation = contracts()
    control = next(item for item in confirmation.variants if item.is_production_baseline)
    baseline = next(item for item in parent.prompt_variants.variants if item.is_production_baseline)
    assert control.model_dump() == baseline.model_dump()


def test_hardened_prompt_requires_atomic_citations() -> None:
    _, confirmation = contracts()
    challenger = next(item for item in confirmation.variants if not item.is_production_baseline)
    assert "separate atomic tokens" in challenger.additional_instructions
    assert "Never combine source identifiers" in challenger.additional_instructions
    assert "first-appearance order" in challenger.additional_instructions


def test_hardened_prompt_handles_partial_evidence() -> None:
    _, confirmation = contracts()
    challenger = next(item for item in confirmation.variants if not item.is_production_baseline)
    assert "supports any material part" in challenger.additional_instructions
    assert "only when no substantive part" in challenger.additional_instructions


def test_plan_contains_twenty_four_attempts() -> None:
    parent, confirmation = contracts()
    plan = build_finalist_plan(parent, confirmation)
    assert len(plan) == 24
    assert len({item.attempt_id for item in plan}) == 24


def test_plan_counterbalances_first_variant() -> None:
    parent, confirmation = contracts()
    plan = build_finalist_plan(parent, confirmation)
    first_by_case = [plan[index].variant_id for index in range(0, len(plan), 2)]
    assert set(first_by_case) == set(confirmation.finalist_ids)


def test_expected_paid_calls_exclude_empty_context() -> None:
    parent, confirmation = contracts()
    assert expected_finalist_api_calls(parent, confirmation) == 22


def test_budget_uses_total_call_ceiling() -> None:
    parent, _ = contracts()
    ledger = FinalistBudgetLedger(
        parent,
        PricingRates(
            generation_input_per_million=0.25,
            generation_output_per_million=2.0,
        ),
        generation_api_calls=59,
        embedding_input_tokens=0,
        generation_input_tokens=0,
        generation_output_tokens=0,
        estimated_cost_usd=0,
    )
    ledger.preflight(estimated_input_tokens=1, maximum_output_tokens=100)
    ledger.record(
        input_tokens=1,
        output_tokens=1,
        fallback_input_tokens=1,
        fallback_output_tokens=100,
    )
    with pytest.raises(FinalistBudgetExceeded, match="live-call"):
        ledger.preflight(estimated_input_tokens=1, maximum_output_tokens=100)


def test_budget_is_not_limited_to_primary_36_calls() -> None:
    parent, _ = contracts()
    ledger = FinalistBudgetLedger(
        parent,
        PricingRates(
            generation_input_per_million=0.25,
            generation_output_per_million=2.0,
        ),
        generation_api_calls=36,
        embedding_input_tokens=0,
        generation_input_tokens=0,
        generation_output_tokens=0,
        estimated_cost_usd=0,
    )
    ledger.preflight(estimated_input_tokens=1, maximum_output_tokens=100)


def test_error_counts_as_zero_score_and_critical_failure() -> None:
    parent, confirmation = contracts()
    plan = build_finalist_plan(parent, confirmation)
    records = {item.attempt_id: record(item) for item in plan}
    failed = plan[0]
    records[failed.attempt_id] = record(failed, status="error")
    summary = aggregate_finalist_records(parent, confirmation, records, {})
    affected = next(item for item in summary["variants"] if item["variant_id"] == failed.variant_id)
    assert affected["response_contract_failures"] == 1
    assert affected["critical_failures"] == 1
    assert affected["critical_failure_rate"] == 0.0833
    assert affected["automated_gate_met"] is False


def test_complete_clean_variant_can_meet_automated_gate() -> None:
    parent, confirmation = contracts()
    plan = build_finalist_plan(parent, confirmation)
    records = {item.attempt_id: record(item, score=4.0) for item in plan}
    summary = aggregate_finalist_records(parent, confirmation, records, {})
    assert summary["complete"] is True
    assert all(item["automated_gate_met"] for item in summary["variants"])


def test_selection_remains_pending_human_review() -> None:
    parent, confirmation = contracts()
    plan = build_finalist_plan(parent, confirmation)
    records = {item.attempt_id: record(item, score=4.0) for item in plan}
    summary = aggregate_finalist_records(parent, confirmation, records, {})
    assert summary["selection_status"] == "pending_blinded_human_review"


def test_incomplete_confirmation_cannot_advance() -> None:
    parent, confirmation = contracts()
    plan = build_finalist_plan(parent, confirmation)
    records = {item.attempt_id: record(item) for item in plan[:-1]}
    summary = aggregate_finalist_records(parent, confirmation, records, {})
    assert summary["complete"] is False
    assert summary["selection_status"] == "confirmation_incomplete"


def test_human_source_evidence_validates(tmp_path: Path) -> None:
    parent, confirmation = contracts()
    summary_path = tmp_path / confirmation.source_human_summary_path
    summary_path.parent.mkdir(parents=True)
    payload = {
        "contract_fingerprint": confirmation.parent_contract_fingerprint,
        "review_set_fingerprint": confirmation.source_human_review_fingerprint,
        "selection_status": "not_performed_phase_6_step_3",
        "attempts_reviewed": 36,
        "variants": [
            {
                "variant_id": "decision_ready_v1",
                "mean_weighted_score": 3.5917,
                "human_threshold_gate_met": False,
            },
            {
                "variant_id": "evidence_first_v1",
                "mean_weighted_score": 2.925,
                "human_threshold_gate_met": False,
            },
            {
                "variant_id": "production_baseline_v1",
                "mean_weighted_score": 3.2833,
                "human_threshold_gate_met": False,
            },
        ],
    }
    summary_path.write_text(json.dumps(payload), encoding="utf-8")
    assert validate_source_human_evidence(tmp_path, parent, confirmation) == payload


def test_wrong_human_review_fingerprint_is_rejected(tmp_path: Path) -> None:
    parent, confirmation = contracts()
    summary_path = tmp_path / confirmation.source_human_summary_path
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(
        json.dumps(
            {
                "contract_fingerprint": confirmation.parent_contract_fingerprint,
                "review_set_fingerprint": "0" * 64,
                "selection_status": "not_performed_phase_6_step_3",
                "attempts_reviewed": 36,
                "variants": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="fingerprint"):
        validate_source_human_evidence(tmp_path, parent, confirmation)
