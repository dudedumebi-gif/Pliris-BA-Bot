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

from evaluation.llm_contexts import FrozenContextBundle, load_frozen_contexts
from evaluation.llm_contract import (
    EvaluationContract,
    ScoringDimension,
    StrictModel,
    contract_fingerprint,
)
from evaluation.llm_runner import RawRunRecord, build_run_plan, load_all_records


class HumanReviewError(RuntimeError):
    """Raised when the blinded human-review contract is violated."""


BLINDING_ALGORITHM = "sha256_case_variant_order_v1"
RESPONSE_FAILURE_TEXT = (
    "[RESPONSE UNAVAILABLE: the original model response failed the strict "
    "citation contract and was not accepted.]"
)
RESPONSE_FAILURE_NOTE = (
    "Original response unavailable because it failed the strict citation contract."
)
DIMENSION_IDS = (
    "groundedness",
    "citation_quality",
    "mode_fulfillment",
    "completeness",
    "relevance_clarity",
    "uncertainty_handling",
)


class BlindAssignment(StrictModel):
    review_id: str = Field(min_length=16)
    attempt_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    response_label: str = Field(pattern=r"^Answer [A-Z]$")
    variant_id: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    response_status: Literal["accepted", "contract_failure"]


class BlindingKey(StrictModel):
    version: int = 1
    contract_fingerprint: str = Field(min_length=64, max_length=64)
    raw_outputs_sha256: str = Field(min_length=64, max_length=64)
    frozen_contexts_sha256: str = Field(min_length=64, max_length=64)
    review_set_fingerprint: str = Field(min_length=64, max_length=64)
    blinding_algorithm: str = Field(min_length=1)
    attempt_count: int = Field(ge=1)
    assignments: tuple[BlindAssignment, ...]


class ValidatedHumanScore(StrictModel):
    review_set_fingerprint: str = Field(min_length=64, max_length=64)
    review_id: str = Field(min_length=16)
    case_id: str = Field(min_length=1)
    response_label: str = Field(pattern=r"^Answer [A-Z]$")
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
class HumanReviewPaths:
    review_csv: Path
    key_json: Path
    scores_csv: Path
    instructions_md: Path
    manifest_json: Path
    summary_json: Path
    summary_md: Path


@dataclass(frozen=True, slots=True)
class PreparedHumanReview:
    paths: HumanReviewPaths
    key: BlindingKey
    review_rows: tuple[dict[str, str], ...]
    score_rows: tuple[dict[str, str], ...]


def human_review_paths(output_root: Path, contract: EvaluationContract) -> HumanReviewPaths:
    review_csv = output_root / contract.config.outputs.blinded_review_csv
    key_json = output_root / contract.config.outputs.blinding_key_json
    scores_csv = output_root / contract.config.outputs.human_scores_csv
    human_dir = review_csv.parent
    return HumanReviewPaths(
        review_csv=review_csv,
        key_json=key_json,
        scores_csv=scores_csv,
        instructions_md=human_dir / "review_instructions.md",
        manifest_json=human_dir / "review_manifest.json",
        summary_json=human_dir / "summary.json",
        summary_md=human_dir / "summary.md",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _review_id(
    fingerprint: str,
    *,
    case_id: str,
    response_label: str,
    repetition: int,
) -> str:
    payload = f"{fingerprint}|human-review-v1|{case_id}|{response_label}|r{repetition}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _ordered_variant_ids(
    fingerprint: str,
    *,
    case_id: str,
    repetition: int,
    variant_ids: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            variant_ids,
            key=lambda variant_id: hashlib.sha256(
                (
                    f"{fingerprint}|{BLINDING_ALGORITHM}|{case_id}|{variant_id}|r{repetition}"
                ).encode()
            ).hexdigest(),
        )
    )


def load_original_primary_records(
    contract: EvaluationContract,
    raw_outputs_path: Path,
) -> dict[str, RawRunRecord]:
    fingerprint = contract_fingerprint(contract)
    records = load_all_records(raw_outputs_path, fingerprint)
    if not records:
        raise HumanReviewError(f"No primary records found: {raw_outputs_path}")

    planned_ids = {item.attempt_id for item in build_run_plan(contract)}
    originals: dict[str, RawRunRecord] = {}
    for record in records:
        if record.attempt_id not in planned_ids:
            raise HumanReviewError(
                f"Primary output contains an attempt outside the frozen plan: {record.attempt_id}"
            )
        originals.setdefault(record.attempt_id, record)

    missing = sorted(planned_ids - set(originals))
    if missing:
        raise HumanReviewError(
            "Primary output is incomplete; missing attempts: " + ", ".join(missing)
        )
    return originals


def build_blind_assignments(
    contract: EvaluationContract,
    records: dict[str, RawRunRecord],
) -> tuple[BlindAssignment, ...]:
    fingerprint = contract_fingerprint(contract)
    variant_ids = tuple(contract.config.variant_ids)
    assignments: list[BlindAssignment] = []

    for repetition in range(1, contract.config.primary_repetitions + 1):
        for case in contract.benchmark.cases:
            ordered = _ordered_variant_ids(
                fingerprint,
                case_id=case.id,
                repetition=repetition,
                variant_ids=variant_ids,
            )
            for index, variant_id in enumerate(ordered):
                label = f"Answer {chr(ord('A') + index)}"
                attempt_id = f"{case.id}::{variant_id}::r{repetition}"
                record = records[attempt_id]
                assignments.append(
                    BlindAssignment(
                        review_id=_review_id(
                            fingerprint,
                            case_id=case.id,
                            response_label=label,
                            repetition=repetition,
                        ),
                        attempt_id=attempt_id,
                        case_id=case.id,
                        response_label=label,
                        variant_id=variant_id,
                        repetition=repetition,
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


def _build_review_rows(
    contract: EvaluationContract,
    bundle: FrozenContextBundle,
    records: dict[str, RawRunRecord],
    assignments: tuple[BlindAssignment, ...],
) -> tuple[dict[str, str], ...]:
    cases = {case.id: case for case in contract.benchmark.cases}
    contexts = bundle.by_case_id()
    rows: list[dict[str, str]] = []

    for assignment in assignments:
        case = cases[assignment.case_id]
        context = contexts[assignment.case_id]
        record = records[assignment.attempt_id]
        response_text = (
            record.answer or ""
            if assignment.response_status == "accepted"
            else RESPONSE_FAILURE_TEXT
        )
        rows.append(
            {
                "review_set_fingerprint": "",
                "review_id": assignment.review_id,
                "case_id": case.id,
                "repetition": str(assignment.repetition),
                "response_label": assignment.response_label,
                "response_status": assignment.response_status,
                "question": case.question,
                "request_mode": case.request_mode.value,
                "context_strategy": case.context_strategy.value,
                "knowledge_base_context": context.context_text,
                "response_text": response_text,
                "minimum_citations": str(case.minimum_citations),
                "minimum_term_groups": str(case.minimum_term_groups),
                "required_term_groups": _term_groups_text(case.required_term_groups),
                "expected_behaviors": _list_text(case.expected_behaviors),
                "forbidden_behaviors": _list_text(case.forbidden_behaviors),
                "expect_insufficient_evidence": str(case.expect_insufficient_evidence).lower(),
            }
        )
    return tuple(rows)


def _review_set_fingerprint(rows: list[dict[str, str]] | tuple[dict[str, str], ...]) -> str:
    payload = [
        {key: value for key, value in row.items() if key != "review_set_fingerprint"}
        for row in rows
    ]
    return _canonical_hash(payload)


def _apply_review_fingerprint(
    rows: tuple[dict[str, str], ...],
    fingerprint: str,
) -> tuple[dict[str, str], ...]:
    return tuple({**row, "review_set_fingerprint": fingerprint} for row in rows)


def _build_score_rows(
    review_rows: tuple[dict[str, str], ...],
) -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for review in review_rows:
        failed = review["response_status"] == "contract_failure"
        rows.append(
            {
                "review_set_fingerprint": review["review_set_fingerprint"],
                "review_id": review["review_id"],
                "case_id": review["case_id"],
                "response_label": review["response_label"],
                "response_status": review["response_status"],
                "groundedness": "0" if failed else "",
                "citation_quality": "0" if failed else "",
                "mode_fulfillment": "0" if failed else "",
                "completeness": "0" if failed else "",
                "relevance_clarity": "0" if failed else "",
                "uncertainty_handling": "0" if failed else "",
                "critical_failure": "true" if failed else "",
                "reviewer_notes": RESPONSE_FAILURE_NOTE if failed else "",
            }
        )
    return tuple(rows)


def build_human_review(
    contract: EvaluationContract,
    bundle: FrozenContextBundle,
    records: dict[str, RawRunRecord],
    *,
    raw_outputs_sha256: str,
    frozen_contexts_sha256: str,
) -> PreparedHumanReview:
    fingerprint = contract_fingerprint(contract)
    if bundle.manifest.contract_fingerprint != fingerprint:
        raise HumanReviewError("Frozen contexts do not match the active evaluation contract.")

    assignments = build_blind_assignments(contract, records)
    base_rows = _build_review_rows(contract, bundle, records, assignments)
    review_fingerprint = _review_set_fingerprint(base_rows)
    review_rows = _apply_review_fingerprint(base_rows, review_fingerprint)
    score_rows = _build_score_rows(review_rows)
    key = BlindingKey(
        contract_fingerprint=fingerprint,
        raw_outputs_sha256=raw_outputs_sha256,
        frozen_contexts_sha256=frozen_contexts_sha256,
        review_set_fingerprint=review_fingerprint,
        blinding_algorithm=BLINDING_ALGORITHM,
        attempt_count=len(assignments),
        assignments=assignments,
    )
    return PreparedHumanReview(
        paths=human_review_paths(Path("."), contract),
        key=key,
        review_rows=review_rows,
        score_rows=score_rows,
    )


_REVIEW_FIELDS = (
    "review_set_fingerprint",
    "review_id",
    "case_id",
    "repetition",
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


def _write_csv(
    path: Path,
    fieldnames: tuple[str, ...],
    rows: tuple[dict[str, str], ...],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _review_instructions(
    contract: EvaluationContract,
    prepared: PreparedHumanReview,
) -> str:
    dimensions = {dimension.id: dimension for dimension in contract.config.scoring_dimensions}
    descriptions = {
        "groundedness": ("Claims are supported by the supplied context and do not invent facts."),
        "citation_quality": (
            "Inline citations are valid, sufficient, and close to the claims they support."
        ),
        "mode_fulfillment": ("The response follows the requested analysis or deliverable mode."),
        "completeness": (
            "The response covers important supported aspects without fabricating missing details."
        ),
        "relevance_clarity": ("The response is direct, organized, and understandable."),
        "uncertainty_handling": (
            "Assumptions, evidence gaps, unresolved conflicts, and conditional claims are "
            "handled appropriately."
        ),
    }
    lines = [
        "# Pliris Phase 6 Blinded Human Review",
        "",
        "Do not open `blinding_key.json` until the score sheet has been completed and saved.",
        "",
        "Review every row in `blinded_responses.csv`, then enter whole-number scores from "
        "0 through 4 in `scores.csv`.",
        "",
        "## Scale",
        "",
        "- 0 — unusable, unsupported, or materially violates the review contract",
        "- 1 — major deficiencies",
        "- 2 — partially meets the criterion",
        "- 3 — solid and substantially meets the criterion",
        "- 4 — excellent and fully meets the criterion",
        "",
        "## Dimensions",
        "",
    ]
    for dimension_id in DIMENSION_IDS:
        dimension = dimensions[dimension_id]
        lines.append(f"- **{dimension_id}** ({dimension.weight:.0%}): {descriptions[dimension_id]}")
    lines.extend(
        [
            "",
            "## Critical failures",
            "",
            "Set `critical_failure` to `true` for a response that is unusable because of "
            "fabrication, missing mandatory evidence, a materially wrong fallback, citation "
            "failure, or another severe contract violation. Add a concise note.",
            "",
            "Rows marked `contract_failure` are intentionally pre-scored 0 across every "
            "dimension and marked as critical failures. Do not change those locked values.",
            "",
            f"The score sheet must contain all {prepared.key.attempt_count} rows. Step 3 does "
            "not select a production prompt.",
            "",
            "Review-set fingerprint:",
            "",
            f"`{prepared.key.review_set_fingerprint}`",
            "",
        ]
    )
    return "\n".join(lines)


def _manifest_payload(prepared: PreparedHumanReview) -> dict[str, Any]:
    failed = sum(row["response_status"] == "contract_failure" for row in prepared.review_rows)
    return {
        "version": 1,
        "contract_fingerprint": prepared.key.contract_fingerprint,
        "review_set_fingerprint": prepared.key.review_set_fingerprint,
        "attempt_count": prepared.key.attempt_count,
        "accepted_response_count": prepared.key.attempt_count - failed,
        "contract_failure_count": failed,
        "response_labels": ["Answer A", "Answer B", "Answer C"],
        "dimension_ids": list(DIMENSION_IDS),
        "score_scale": {"minimum": 0, "maximum": 4},
        "selection_status": "not_performed_phase_6_step_3",
    }


def prepare_human_review(
    repo_root: Path,
    *,
    overwrite: bool = False,
) -> PreparedHumanReview:
    from evaluation.llm_contract import deterministic_output_root, load_evaluation_contract

    root = repo_root.resolve()
    contract = load_evaluation_contract(root)
    output_root = deterministic_output_root(root, contract)
    paths = human_review_paths(output_root, contract)
    raw_path = output_root / contract.config.outputs.raw_outputs_jsonl
    frozen_path = output_root / contract.config.outputs.frozen_contexts_jsonl

    required_outputs = (
        paths.review_csv,
        paths.key_json,
        paths.scores_csv,
        paths.instructions_md,
        paths.manifest_json,
    )
    existing = [path for path in required_outputs if path.exists()]
    if existing and not overwrite:
        raise HumanReviewError(
            "Human-review files already exist. Use the explicit overwrite option only "
            "before scoring begins: " + ", ".join(str(path) for path in existing)
        )

    records = load_original_primary_records(contract, raw_path)
    bundle = load_frozen_contexts(frozen_path, contract)
    prepared_base = build_human_review(
        contract,
        bundle,
        records,
        raw_outputs_sha256=_sha256_file(raw_path),
        frozen_contexts_sha256=_sha256_file(frozen_path),
    )
    prepared = PreparedHumanReview(
        paths=paths,
        key=prepared_base.key,
        review_rows=prepared_base.review_rows,
        score_rows=prepared_base.score_rows,
    )

    _write_csv(paths.review_csv, _REVIEW_FIELDS, prepared.review_rows)
    _write_csv(paths.scores_csv, _SCORE_FIELDS, prepared.score_rows)
    paths.key_json.parent.mkdir(parents=True, exist_ok=True)
    paths.key_json.write_text(
        json.dumps(
            prepared.key.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    paths.instructions_md.write_text(
        _review_instructions(contract, prepared),
        encoding="utf-8",
    )
    paths.manifest_json.write_text(
        json.dumps(
            _manifest_payload(prepared),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    for summary_path in (paths.summary_json, paths.summary_md):
        if summary_path.exists() and overwrite:
            summary_path.unlink()

    return prepared


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError as exc:
        raise HumanReviewError(f"Human-review file not found: {path}") from exc


def _parse_bool(value: str, *, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise HumanReviewError(f"{field_name} must be true or false; received {value!r}.")


def _parse_score(
    value: str,
    *,
    review_id: str,
    dimension_id: str,
) -> int:
    normalized = value.strip()
    if normalized == "":
        raise HumanReviewError(f"Missing {dimension_id} score for {review_id}.")
    if normalized not in {"0", "1", "2", "3", "4"}:
        raise HumanReviewError(
            f"{dimension_id} for {review_id} must be a whole number from 0 through 4."
        )
    return int(normalized)


def load_blinding_key(path: Path) -> BlindingKey:
    try:
        return BlindingKey.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HumanReviewError(f"Blinding key not found: {path}") from exc
    except Exception as exc:
        raise HumanReviewError(f"Blinding key is invalid: {path}") from exc


def validate_human_scores(
    scores_path: Path,
    review_csv_path: Path,
    key: BlindingKey,
) -> tuple[ValidatedHumanScore, ...]:
    reviews = _read_csv(review_csv_path)
    scores = _read_csv(scores_path)
    if _review_set_fingerprint(reviews) != key.review_set_fingerprint:
        raise HumanReviewError("Blinded review content failed fingerprint validation.")

    review_by_id = {row["review_id"]: row for row in reviews}
    if len(review_by_id) != len(reviews):
        raise HumanReviewError("Blinded review ids must be unique.")
    if len(scores) != key.attempt_count:
        raise HumanReviewError(
            f"Score sheet must contain exactly {key.attempt_count} rows; found {len(scores)}."
        )

    score_ids = [row.get("review_id", "") for row in scores]
    if len(score_ids) != len(set(score_ids)):
        raise HumanReviewError("Score sheet review ids must be unique.")
    if set(score_ids) != set(review_by_id):
        missing = sorted(set(review_by_id) - set(score_ids))
        unknown = sorted(set(score_ids) - set(review_by_id))
        raise HumanReviewError(
            "Score sheet ids do not match the blinded review; "
            f"missing={missing}, unknown={unknown}."
        )

    validated: list[ValidatedHumanScore] = []
    for row in scores:
        review_id = row["review_id"]
        review = review_by_id[review_id]
        if (
            row.get("review_set_fingerprint", "") != key.review_set_fingerprint
            or review.get("review_set_fingerprint", "") != key.review_set_fingerprint
        ):
            raise HumanReviewError(f"Review-set fingerprint mismatch for {review_id}.")
        for field_name in ("case_id", "response_label", "response_status"):
            if row.get(field_name, "") != review.get(field_name, ""):
                raise HumanReviewError(f"{field_name} mismatch for {review_id}.")

        parsed_scores = {
            dimension_id: _parse_score(
                row.get(dimension_id, ""),
                review_id=review_id,
                dimension_id=dimension_id,
            )
            for dimension_id in DIMENSION_IDS
        }
        critical = _parse_bool(
            row.get("critical_failure", ""),
            field_name=f"critical_failure for {review_id}",
        )
        notes = row.get("reviewer_notes", "").strip()
        response_status = review["response_status"]

        if response_status == "contract_failure":
            if any(parsed_scores.values()) or not critical:
                raise HumanReviewError(
                    f"Contract-failure rows must remain scored 0 and critical for {review_id}."
                )
            if notes != RESPONSE_FAILURE_NOTE:
                raise HumanReviewError(
                    f"Contract-failure reviewer note must remain unchanged for {review_id}."
                )
        elif critical and not notes:
            raise HumanReviewError(
                f"Accepted responses marked critical require a reviewer note: {review_id}."
            )

        validated.append(
            ValidatedHumanScore(
                review_set_fingerprint=key.review_set_fingerprint,
                review_id=review_id,
                case_id=review["case_id"],
                response_label=review["response_label"],
                response_status=response_status,
                critical_failure=critical,
                reviewer_notes=notes,
                **parsed_scores,
            )
        )
    return tuple(validated)


def _weighted_score(
    score: ValidatedHumanScore,
    dimensions: tuple[ScoringDimension, ...],
) -> float:
    return round(
        sum(getattr(score, dimension.id) * dimension.weight for dimension in dimensions),
        4,
    )


def summarize_human_scores(
    contract: EvaluationContract,
    key: BlindingKey,
    scores: tuple[ValidatedHumanScore, ...],
    *,
    reviewer_id: str,
) -> dict[str, Any]:
    normalized_reviewer = reviewer_id.strip()
    if not normalized_reviewer:
        raise HumanReviewError("reviewer_id must not be blank.")

    assignment_by_review_id = {item.review_id: item for item in key.assignments}
    grouped: dict[str, list[ValidatedHumanScore]] = defaultdict(list)
    for score in scores:
        assignment = assignment_by_review_id.get(score.review_id)
        if assignment is None:
            raise HumanReviewError(f"Score row is absent from the blinding key: {score.review_id}")
        grouped[assignment.variant_id].append(score)

    variants: list[dict[str, Any]] = []
    dimensions = contract.config.scoring_dimensions
    expected_per_variant = len(contract.benchmark.cases) * contract.config.primary_repetitions
    for variant_id in sorted(contract.config.variant_ids):
        variant_scores = grouped[variant_id]
        if len(variant_scores) != expected_per_variant:
            raise HumanReviewError(f"Variant {variant_id!r} has incomplete human scores.")

        weighted = [_weighted_score(score, dimensions) for score in variant_scores]
        critical_count = sum(score.critical_failure for score in variant_scores)
        failure_count = sum(score.response_status == "contract_failure" for score in variant_scores)
        pass_count = sum(
            not score.critical_failure
            and item_score >= contract.config.thresholds.human_weighted_score_min
            for score, item_score in zip(variant_scores, weighted, strict=True)
        )
        mean_weighted = round(sum(weighted) / len(weighted), 4)
        critical_rate = round(critical_count / len(variant_scores), 4)
        dimension_means = {
            dimension.id: round(
                sum(getattr(score, dimension.id) for score in variant_scores) / len(variant_scores),
                4,
            )
            for dimension in dimensions
        }
        variants.append(
            {
                "variant_id": variant_id,
                "attempts_reviewed": len(variant_scores),
                "response_contract_failures": failure_count,
                "reviewer_critical_failures": critical_count,
                "critical_failure_rate": critical_rate,
                "mean_weighted_score": mean_weighted,
                "human_pass_rate": round(pass_count / len(variant_scores), 4),
                "dimension_means": dimension_means,
                "human_threshold_gate_met": (
                    mean_weighted >= contract.config.thresholds.human_weighted_score_min
                    and critical_rate <= contract.config.thresholds.critical_failure_rate_max
                ),
            }
        )

    return {
        "contract_fingerprint": contract_fingerprint(contract),
        "review_set_fingerprint": key.review_set_fingerprint,
        "reviewer_id": normalized_reviewer,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "attempts_reviewed": len(scores),
        "selection_status": "not_performed_phase_6_step_3",
        "thresholds": {
            "human_weighted_score_min": (contract.config.thresholds.human_weighted_score_min),
            "critical_failure_rate_max": (contract.config.thresholds.critical_failure_rate_max),
        },
        "variants": variants,
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Pliris Prompt Comparison — Blinded Human Review",
        "",
        "> Phase 6 Step 3 does not select a production prompt.",
        "",
        f"- Reviewer: `{summary['reviewer_id']}`",
        f"- Attempts reviewed: `{summary['attempts_reviewed']}`",
        f"- Review-set fingerprint: `{summary['review_set_fingerprint']}`",
        "",
        "## Unblinded aggregate results",
        "",
        "| Variant | Reviewed | Response failures | Critical failures | Mean score | "
        "Pass rate | Threshold gate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant in summary["variants"]:
        lines.append(
            "| "
            f"{variant['variant_id']} | "
            f"{variant['attempts_reviewed']} | "
            f"{variant['response_contract_failures']} | "
            f"{variant['reviewer_critical_failures']} | "
            f"{variant['mean_weighted_score']} | "
            f"{variant['human_pass_rate']} | "
            f"{variant['human_threshold_gate_met']} |"
        )
    lines.extend(
        [
            "",
            "These aggregate results are evidence for Step 4. They do not select or modify "
            "the production prompt.",
            "",
        ]
    )
    return "\n".join(lines)


def finalize_human_review(
    repo_root: Path,
    *,
    reviewer_id: str,
) -> dict[str, Any]:
    from evaluation.llm_contract import deterministic_output_root, load_evaluation_contract

    root = repo_root.resolve()
    contract = load_evaluation_contract(root)
    output_root = deterministic_output_root(root, contract)
    paths = human_review_paths(output_root, contract)
    raw_path = output_root / contract.config.outputs.raw_outputs_jsonl
    frozen_path = output_root / contract.config.outputs.frozen_contexts_jsonl
    key = load_blinding_key(paths.key_json)

    if key.contract_fingerprint != contract_fingerprint(contract):
        raise HumanReviewError("Blinding key does not match the active contract.")
    if _sha256_file(raw_path) != key.raw_outputs_sha256:
        raise HumanReviewError("Primary raw outputs changed after the review set was prepared.")
    if _sha256_file(frozen_path) != key.frozen_contexts_sha256:
        raise HumanReviewError("Frozen contexts changed after the review set was prepared.")

    scores = validate_human_scores(paths.scores_csv, paths.review_csv, key)
    summary = summarize_human_scores(
        contract,
        key,
        scores,
        reviewer_id=reviewer_id,
    )
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths.summary_md.write_text(_summary_markdown(summary), encoding="utf-8")
    return summary
