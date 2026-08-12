from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from evaluation.llm_contexts import load_frozen_contexts
from evaluation.llm_contract import ScoringDimension, StrictModel, load_evaluation_contract
from evaluation.llm_finalist_contract import (
    FinalistConfirmationContract,
    finalist_contract_fingerprint,
    finalist_output_root,
    load_finalist_confirmation_contract,
)
from evaluation.llm_runner import RawRunRecord, load_all_records

DIMENSION_IDS = (
    "groundedness",
    "citation_quality",
    "mode_fulfillment",
    "completeness",
    "relevance_clarity",
    "uncertainty_handling",
)
BLINDING_ALGORITHM = "sha256_finalist_case_order_v1"
RESPONSE_FAILURE_TEXT = (
    "[RESPONSE UNAVAILABLE: the original finalist response failed the strict "
    "citation contract and was not accepted.]"
)
RESPONSE_FAILURE_NOTE = (
    "Original finalist response unavailable because it failed the strict citation contract."
)


class FinalistHumanReviewError(RuntimeError):
    """Raised when the finalist diagnostic-review contract is violated."""


class FinalistBlindAssignment(StrictModel):
    review_id: str = Field(min_length=16)
    attempt_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    response_label: str = Field(pattern=r"^Answer [AB]$")
    variant_id: str = Field(min_length=1)
    response_status: Literal["accepted", "contract_failure"]


class FinalistBlindingKey(StrictModel):
    version: int = 1
    finalist_contract_fingerprint: str = Field(min_length=64, max_length=64)
    raw_outputs_sha256: str = Field(min_length=64, max_length=64)
    frozen_contexts_sha256: str = Field(min_length=64, max_length=64)
    automated_summary_sha256: str = Field(min_length=64, max_length=64)
    review_set_fingerprint: str = Field(min_length=64, max_length=64)
    blinding_algorithm: str = Field(min_length=1)
    attempt_count: int = Field(ge=1)
    assignments: tuple[FinalistBlindAssignment, ...]


class ValidatedFinalistScore(StrictModel):
    review_set_fingerprint: str = Field(min_length=64, max_length=64)
    review_id: str = Field(min_length=16)
    case_id: str = Field(min_length=1)
    response_label: str = Field(pattern=r"^Answer [AB]$")
    response_status: Literal["accepted", "contract_failure"]
    groundedness: int = Field(ge=0, le=4)
    citation_quality: int = Field(ge=0, le=4)
    mode_fulfillment: int = Field(ge=0, le=4)
    completeness: int = Field(ge=0, le=4)
    relevance_clarity: int = Field(ge=0, le=4)
    uncertainty_handling: int = Field(ge=0, le=4)
    critical_failure: bool
    reviewer_notes: str = ""


@dataclass(frozen=True, slots=True)
class FinalistReviewPaths:
    review_csv: Path
    key_json: Path
    scores_csv: Path
    instructions_md: Path
    manifest_json: Path
    summary_json: Path
    summary_md: Path
    decision_json: Path
    decision_md: Path


def finalist_review_paths(output_root: Path) -> FinalistReviewPaths:
    human = output_root / "human_review"
    return FinalistReviewPaths(
        review_csv=human / "blinded_responses.csv",
        key_json=human / "blinding_key.json",
        scores_csv=human / "scores.csv",
        instructions_md=human / "review_instructions.md",
        manifest_json=human / "review_manifest.json",
        summary_json=human / "summary.json",
        summary_md=human / "summary.md",
        decision_json=human / "decision_record.json",
        decision_md=human / "decision_record.md",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except FileNotFoundError as exc:
        raise FinalistHumanReviewError(f"Required evidence file not found: {path}") from exc
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _review_id(fingerprint: str, case_id: str, response_label: str) -> str:
    raw = f"{fingerprint}|finalist-human-v1|{case_id}|{response_label}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _ordered_variant_ids(
    fingerprint: str,
    case_id: str,
    variant_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            variant_ids,
            key=lambda variant_id: hashlib.sha256(
                f"{fingerprint}|{BLINDING_ALGORITHM}|{case_id}|{variant_id}".encode()
            ).hexdigest(),
        )
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FinalistHumanReviewError(f"Required JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FinalistHumanReviewError(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise FinalistHumanReviewError(f"Expected JSON object: {path}")
    return payload


def load_finalist_records(
    confirmation: FinalistConfirmationContract,
    raw_path: Path,
) -> dict[str, RawRunRecord]:
    fingerprint = finalist_contract_fingerprint(confirmation)
    records = load_all_records(raw_path, fingerprint)
    originals: dict[str, RawRunRecord] = {}
    for record in records:
        originals.setdefault(record.attempt_id, record)
    expected = {
        f"{case_id}::{variant_id}::confirmation-r1"
        for case_id in _case_ids_from_records(records)
        for variant_id in confirmation.finalist_ids
    }
    if len(originals) != 24 or set(originals) != expected:
        raise FinalistHumanReviewError(
            "Finalist output must contain exactly 24 frozen first-run attempts; "
            f"found {len(originals)}."
        )
    return originals


def _case_ids_from_records(records: tuple[RawRunRecord, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(record.case_id for record in records))


def build_assignments(
    confirmation: FinalistConfirmationContract,
    case_ids: tuple[str, ...],
    records: dict[str, RawRunRecord],
) -> tuple[FinalistBlindAssignment, ...]:
    fingerprint = finalist_contract_fingerprint(confirmation)
    assignments: list[FinalistBlindAssignment] = []
    for case_id in case_ids:
        ordered = _ordered_variant_ids(fingerprint, case_id, confirmation.finalist_ids)
        for index, variant_id in enumerate(ordered):
            label = f"Answer {chr(ord('A') + index)}"
            attempt_id = f"{case_id}::{variant_id}::confirmation-r1"
            record = records[attempt_id]
            assignments.append(
                FinalistBlindAssignment(
                    review_id=_review_id(fingerprint, case_id, label),
                    attempt_id=attempt_id,
                    case_id=case_id,
                    response_label=label,
                    variant_id=variant_id,
                    response_status=(
                        "accepted" if record.status == "success" else "contract_failure"
                    ),
                )
            )
    return tuple(assignments)


def _list_text(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _term_groups_text(groups: tuple[tuple[str, ...], ...]) -> str:
    return "\n".join(f"- {' OR '.join(group)}" for group in groups)


def _review_set_fingerprint(rows: list[dict[str, str]]) -> str:
    return _canonical_hash(
        [{k: v for k, v in row.items() if k != "review_set_fingerprint"} for row in rows]
    )


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


_REVIEW_FIELDS = (
    "review_set_fingerprint",
    "review_id",
    "case_id",
    "response_label",
    "response_status",
    "question",
    "request_mode",
    "context_strategy",
    "knowledge_base_context",
    "response_text",
    "minimum_citations",
    "minimum_term_groups",
    "required_term_groups",
    "expected_behaviors",
    "forbidden_behaviors",
    "expect_insufficient_evidence",
)
_SCORE_FIELDS = (
    "review_set_fingerprint",
    "review_id",
    "case_id",
    "response_label",
    "response_status",
    *DIMENSION_IDS,
    "critical_failure",
    "reviewer_notes",
)


def prepare_finalist_review(repo_root: Path, *, overwrite: bool = False) -> FinalistBlindingKey:
    root = repo_root.resolve()
    parent = load_evaluation_contract(root)
    confirmation = load_finalist_confirmation_contract(root, parent)
    output_root = finalist_output_root(root, confirmation)
    paths = finalist_review_paths(output_root)
    raw_path = output_root / confirmation.outputs.raw_outputs_jsonl
    automated_summary_path = output_root / confirmation.outputs.automated_summary_json
    frozen_path = root / parent.config.outputs.root / parent.config.outputs.frozen_contexts_jsonl

    required = (
        paths.review_csv,
        paths.key_json,
        paths.scores_csv,
        paths.instructions_md,
        paths.manifest_json,
    )
    existing = [path for path in required if path.exists()]
    if existing and not overwrite:
        raise FinalistHumanReviewError(
            "Finalist-review files already exist. Use --overwrite only before scoring begins."
        )

    automated = _load_json(automated_summary_path)
    if not automated.get("complete") or automated.get("recorded_attempts") != 24:
        raise FinalistHumanReviewError("Finalist confirmation is incomplete.")
    if any(bool(item.get("automated_gate_met")) for item in automated.get("variants", [])):
        raise FinalistHumanReviewError(
            "Diagnostic workflow expects every finalist automated gate to fail."
        )

    records = load_finalist_records(confirmation, raw_path)
    bundle = load_frozen_contexts(frozen_path, parent)
    cases = {case.id: case for case in parent.benchmark.cases}
    contexts = bundle.by_case_id()
    case_ids = tuple(case.id for case in parent.benchmark.cases)
    assignments = build_assignments(confirmation, case_ids, records)

    review_rows: list[dict[str, str]] = []
    for assignment in assignments:
        case = cases[assignment.case_id]
        context = contexts[assignment.case_id]
        record = records[assignment.attempt_id]
        review_rows.append(
            {
                "review_set_fingerprint": "",
                "review_id": assignment.review_id,
                "case_id": assignment.case_id,
                "response_label": assignment.response_label,
                "response_status": assignment.response_status,
                "question": case.question,
                "request_mode": case.request_mode.value,
                "context_strategy": case.context_strategy.value,
                "knowledge_base_context": context.context_text,
                "response_text": (
                    record.answer or ""
                    if assignment.response_status == "accepted"
                    else RESPONSE_FAILURE_TEXT
                ),
                "minimum_citations": str(case.minimum_citations),
                "minimum_term_groups": str(case.minimum_term_groups),
                "required_term_groups": _term_groups_text(case.required_term_groups),
                "expected_behaviors": _list_text(case.expected_behaviors),
                "forbidden_behaviors": _list_text(case.forbidden_behaviors),
                "expect_insufficient_evidence": str(case.expect_insufficient_evidence).lower(),
            }
        )
    review_fingerprint = _review_set_fingerprint(review_rows)
    for row in review_rows:
        row["review_set_fingerprint"] = review_fingerprint

    score_rows: list[dict[str, str]] = []
    for row in review_rows:
        failed = row["response_status"] == "contract_failure"
        score_rows.append(
            {
                "review_set_fingerprint": review_fingerprint,
                "review_id": row["review_id"],
                "case_id": row["case_id"],
                "response_label": row["response_label"],
                "response_status": row["response_status"],
                **{dimension: "0" if failed else "" for dimension in DIMENSION_IDS},
                "critical_failure": "true" if failed else "",
                "reviewer_notes": RESPONSE_FAILURE_NOTE if failed else "",
            }
        )

    key = FinalistBlindingKey(
        finalist_contract_fingerprint=finalist_contract_fingerprint(confirmation),
        raw_outputs_sha256=_sha256_file(raw_path),
        frozen_contexts_sha256=_sha256_file(frozen_path),
        automated_summary_sha256=_sha256_file(automated_summary_path),
        review_set_fingerprint=review_fingerprint,
        blinding_algorithm=BLINDING_ALGORITHM,
        attempt_count=len(assignments),
        assignments=assignments,
    )
    _write_csv(paths.review_csv, _REVIEW_FIELDS, review_rows)
    _write_csv(paths.scores_csv, _SCORE_FIELDS, score_rows)
    paths.key_json.parent.mkdir(parents=True, exist_ok=True)
    paths.key_json.write_text(
        json.dumps(key.model_dump(mode="json"), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    failures = sum(item.response_status == "contract_failure" for item in assignments)
    manifest = {
        "version": 1,
        "finalist_contract_fingerprint": key.finalist_contract_fingerprint,
        "review_set_fingerprint": review_fingerprint,
        "attempt_count": len(assignments),
        "accepted_response_count": len(assignments) - failures,
        "contract_failure_count": failures,
        "response_labels": ["Answer A", "Answer B"],
        "dimension_ids": list(DIMENSION_IDS),
        "selection_status": "diagnostic_review_pending",
    }
    paths.manifest_json.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    instructions = f"""# Pliris Phase 6 Step 4B — Blinded Finalist Diagnostic Review

Do not open `blinding_key.json` until finalization succeeds.

Review every row in `blinded_responses.csv`, then enter whole-number scores
from 0 through 4 in `scores.csv`.

Scale: 0 unusable; 1 major deficiencies; 2 partial; 3 solid; 4 excellent.

Dimensions:
- groundedness
- citation_quality
- mode_fulfillment
- completeness
- relevance_clarity
- uncertainty_handling

Set `critical_failure` to `true` only for an unusable response and add a
concise note. Contract-failure rows are locked to zero scores, `true`, and
the generated note; do not change them.

This is diagnostic review. Human scores cannot override a failed automated
gate and cannot select a production prompt.

Review-set fingerprint:

`{review_fingerprint}`
"""
    paths.instructions_md.write_text(instructions, encoding="utf-8")
    for path in (paths.summary_json, paths.summary_md, paths.decision_json, paths.decision_md):
        if overwrite and path.exists():
            path.unlink()
    return key


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError as exc:
        raise FinalistHumanReviewError(f"Review file not found: {path}") from exc


def _parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise FinalistHumanReviewError(f"{field_name} must be true or false.")


def _parse_score(value: str, review_id: str, dimension: str) -> int:
    normalized = value.strip()
    if normalized not in {"0", "1", "2", "3", "4"}:
        raise FinalistHumanReviewError(
            f"{dimension} for {review_id} must be a whole number from 0 through 4."
        )
    return int(normalized)


def load_key(path: Path) -> FinalistBlindingKey:
    try:
        return FinalistBlindingKey.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FinalistHumanReviewError(f"Invalid finalist blinding key: {path}") from exc


def validate_scores(
    scores_path: Path,
    review_path: Path,
    key: FinalistBlindingKey,
) -> tuple[ValidatedFinalistScore, ...]:
    reviews = _read_csv(review_path)
    scores = _read_csv(scores_path)
    if _review_set_fingerprint(reviews) != key.review_set_fingerprint:
        raise FinalistHumanReviewError("Blinded finalist review failed fingerprint validation.")
    review_by_id = {row["review_id"]: row for row in reviews}
    if len(review_by_id) != len(reviews) or len(scores) != key.attempt_count:
        raise FinalistHumanReviewError("Finalist score sheet is incomplete or has duplicate ids.")
    if {row.get("review_id", "") for row in scores} != set(review_by_id):
        raise FinalistHumanReviewError("Finalist score-sheet ids do not match the review set.")

    validated: list[ValidatedFinalistScore] = []
    for row in scores:
        review_id = row["review_id"]
        review = review_by_id[review_id]
        for field in (
            "review_set_fingerprint",
            "case_id",
            "response_label",
            "response_status",
        ):
            expected = (
                key.review_set_fingerprint if field == "review_set_fingerprint" else review[field]
            )
            if row.get(field, "") != expected:
                raise FinalistHumanReviewError(f"{field} mismatch for {review_id}.")
        parsed = {
            dimension: _parse_score(row.get(dimension, ""), review_id, dimension)
            for dimension in DIMENSION_IDS
        }
        critical = _parse_bool(row.get("critical_failure", ""), f"critical_failure for {review_id}")
        notes = row.get("reviewer_notes", "").strip()
        if review["response_status"] == "contract_failure":
            if any(parsed.values()) or not critical or notes != RESPONSE_FAILURE_NOTE:
                raise FinalistHumanReviewError(
                    f"Contract-failure row is not locked correctly: {review_id}."
                )
        elif critical and not notes:
            raise FinalistHumanReviewError(
                f"Accepted critical response requires a reviewer note: {review_id}."
            )
        validated.append(
            ValidatedFinalistScore(
                review_set_fingerprint=key.review_set_fingerprint,
                review_id=review_id,
                case_id=review["case_id"],
                response_label=review["response_label"],
                response_status=review["response_status"],
                critical_failure=critical,
                reviewer_notes=notes,
                **parsed,
            )
        )
    return tuple(validated)


def _weighted_score(
    score: ValidatedFinalistScore,
    dimensions: tuple[ScoringDimension, ...],
) -> float:
    return round(sum(getattr(score, item.id) * item.weight for item in dimensions), 4)


def finalize_finalist_review(repo_root: Path, *, reviewer_id: str) -> dict[str, Any]:
    root = repo_root.resolve()
    parent = load_evaluation_contract(root)
    confirmation = load_finalist_confirmation_contract(root, parent)
    output_root = finalist_output_root(root, confirmation)
    paths = finalist_review_paths(output_root)
    raw_path = output_root / confirmation.outputs.raw_outputs_jsonl
    automated_path = output_root / confirmation.outputs.automated_summary_json
    frozen_path = root / parent.config.outputs.root / parent.config.outputs.frozen_contexts_jsonl
    key = load_key(paths.key_json)

    if key.finalist_contract_fingerprint != finalist_contract_fingerprint(confirmation):
        raise FinalistHumanReviewError("Blinding key does not match the finalist contract.")
    if _sha256_file(raw_path) != key.raw_outputs_sha256:
        raise FinalistHumanReviewError("Finalist raw outputs changed after preparation.")
    if _sha256_file(frozen_path) != key.frozen_contexts_sha256:
        raise FinalistHumanReviewError("Frozen contexts changed after preparation.")
    if _sha256_file(automated_path) != key.automated_summary_sha256:
        raise FinalistHumanReviewError("Automated finalist summary changed after preparation.")

    reviewer = reviewer_id.strip()
    if not reviewer:
        raise FinalistHumanReviewError("reviewer_id must not be blank.")
    scores = validate_scores(paths.scores_csv, paths.review_csv, key)
    assignment_by_id = {item.review_id: item for item in key.assignments}
    grouped: dict[str, list[ValidatedFinalistScore]] = defaultdict(list)
    for score in scores:
        grouped[assignment_by_id[score.review_id].variant_id].append(score)

    automated = _load_json(automated_path)
    automated_by_id = {item["variant_id"]: item for item in automated["variants"]}
    variants: list[dict[str, Any]] = []
    for variant_id in sorted(confirmation.finalist_ids):
        variant_scores = grouped[variant_id]
        if len(variant_scores) != 12:
            raise FinalistHumanReviewError(f"Incomplete scores for {variant_id}.")
        weighted = [
            _weighted_score(score, parent.config.scoring_dimensions) for score in variant_scores
        ]
        critical_count = sum(score.critical_failure for score in variant_scores)
        mean_score = round(sum(weighted) / len(weighted), 4)
        critical_rate = round(critical_count / len(variant_scores), 4)
        human_gate = bool(
            mean_score >= parent.config.thresholds.human_weighted_score_min
            and critical_rate <= confirmation.selection_policy.critical_failure_rate_max
        )
        automated_gate = bool(automated_by_id[variant_id]["automated_gate_met"])
        variants.append(
            {
                "variant_id": variant_id,
                "attempts_reviewed": len(variant_scores),
                "response_contract_failures": sum(
                    score.response_status == "contract_failure" for score in variant_scores
                ),
                "reviewer_critical_failures": critical_count,
                "critical_failure_rate": critical_rate,
                "mean_weighted_score": mean_score,
                "human_pass_rate": round(
                    sum(
                        not score.critical_failure
                        and item >= parent.config.thresholds.human_weighted_score_min
                        for score, item in zip(variant_scores, weighted, strict=True)
                    )
                    / len(variant_scores),
                    4,
                ),
                "human_gate_met": human_gate,
                "automated_gate_met": automated_gate,
                "combined_gate_met": automated_gate and human_gate,
                "dimension_means": {
                    dimension.id: round(
                        sum(getattr(score, dimension.id) for score in variant_scores)
                        / len(variant_scores),
                        4,
                    )
                    for dimension in parent.config.scoring_dimensions
                },
            }
        )

    summary = {
        "finalist_contract_fingerprint": key.finalist_contract_fingerprint,
        "review_set_fingerprint": key.review_set_fingerprint,
        "reviewer_id": reviewer,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "attempts_reviewed": len(scores),
        "selection_status": "diagnostic_review_complete",
        "variants": variants,
    }
    eligible = [item for item in variants if item["combined_gate_met"]]
    selected = (
        max(eligible, key=lambda item: item["mean_weighted_score"])["variant_id"]
        if eligible
        else None
    )
    decision = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "decision_status": "finalist_selected" if selected else "no_finalist_selected",
        "selected_variant_id": selected,
        "retained_production_prompt": confirmation.control_variant_id
        if selected is None
        else selected,
        "retention_reason": (
            "No finalist met both the frozen automated and human gates. The existing production "
            "baseline remains unchanged as a no-change safety decision; "
            "this does not mean it passed."
            if selected is None
            else "Selected finalist met both frozen gates."
        ),
        "production_prompt_changed": selected is not None
        and selected != confirmation.control_variant_id,
        "human_review_cannot_override_automated_gate": True,
        "variants": variants,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths.decision_json.write_text(
        json.dumps(decision, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_lines = [
        "# Pliris Finalist Diagnostic Human Review",
        "",
        f"- Reviewer: `{reviewer}`",
        f"- Attempts reviewed: `{len(scores)}`",
        "- Selection status: `diagnostic_review_complete`",
        "",
        "| Finalist | Mean score | Critical rate | Human gate | Automated gate | Combined gate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in variants:
        summary_lines.append(
            f"| {item['variant_id']} | {item['mean_weighted_score']} | "
            f"{item['critical_failure_rate']} | {item['human_gate_met']} | "
            f"{item['automated_gate_met']} | {item['combined_gate_met']} |"
        )
    paths.summary_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    decision_lines = [
        "# Pliris Production-Prompt Decision Record",
        "",
        f"- Decision: `{decision['decision_status']}`",
        f"- Selected finalist: `{selected}`",
        f"- Retained prompt: `{decision['retained_production_prompt']}`",
        f"- Production prompt changed: `{decision['production_prompt_changed']}`",
        "",
        decision["retention_reason"],
        "",
    ]
    paths.decision_md.write_text("\n".join(decision_lines), encoding="utf-8")
    return {"summary": summary, "decision": decision, "paths": paths}
