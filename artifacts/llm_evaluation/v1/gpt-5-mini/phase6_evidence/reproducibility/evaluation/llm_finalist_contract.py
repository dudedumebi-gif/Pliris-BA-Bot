from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from evaluation.llm_contract import (
    EvaluationContract,
    PromptVariant,
    StrictModel,
    contract_fingerprint,
)


class FinalistSelectionPolicy(StrictModel):
    automated_weighted_score_min: float
    critical_failure_rate_max: float = Field(ge=0, le=1)
    response_contract_failure_max: int = Field(ge=0)
    human_review_required: bool
    require_complete_confirmation: bool


class FinalistOutputPaths(StrictModel):
    root: str = Field(min_length=1)
    raw_outputs_jsonl: str = Field(min_length=1)
    automated_scores_csv: str = Field(min_length=1)
    automated_summary_json: str = Field(min_length=1)
    automated_summary_md: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_paths(self) -> Self:
        for field_name, value in self.model_dump().items():
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{field_name} must be a safe relative path")
        return self


class FinalistConfirmationContract(StrictModel):
    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    parent_contract_fingerprint: str = Field(min_length=64, max_length=64)
    source_human_review_fingerprint: str = Field(min_length=64, max_length=64)
    source_human_summary_path: str = Field(min_length=1)
    source_candidate_id: str = Field(min_length=1)
    control_variant_id: str = Field(min_length=1)
    repetitions: int = Field(ge=1)
    variants: tuple[PromptVariant, ...] = Field(min_length=2, max_length=2)
    selection_policy: FinalistSelectionPolicy
    outputs: FinalistOutputPaths

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        ids = [variant.id for variant in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("finalist variant ids must be unique")
        if self.control_variant_id not in ids:
            raise ValueError("control_variant_id must be a finalist")
        if self.source_candidate_id == self.control_variant_id:
            raise ValueError("source candidate and control must differ")

        controls = [variant for variant in self.variants if variant.is_production_baseline]
        if len(controls) != 1:
            raise ValueError("exactly one unchanged production baseline control is required")
        if controls[0].id != self.control_variant_id:
            raise ValueError("the production baseline must be the configured control")
        if controls[0].additional_instructions.strip():
            raise ValueError("the production baseline control must remain unchanged")

        challengers = [variant for variant in self.variants if not variant.is_production_baseline]
        if len(challengers) != 1 or not challengers[0].additional_instructions.strip():
            raise ValueError("exactly one hardened challenger is required")
        if self.selection_policy.response_contract_failure_max != 0:
            raise ValueError("finalist confirmation must require zero response-contract failures")
        if not self.selection_policy.human_review_required:
            raise ValueError("finalist confirmation requires blinded human review")
        if not self.selection_policy.require_complete_confirmation:
            raise ValueError("finalist confirmation must be complete before selection")

        summary_path = Path(self.source_human_summary_path)
        if summary_path.is_absolute() or ".." in summary_path.parts:
            raise ValueError("source_human_summary_path must be a safe relative path")
        return self

    @property
    def finalist_ids(self) -> tuple[str, ...]:
        return tuple(variant.id for variant in self.variants)


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"finalist confirmation file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"finalist confirmation file is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("finalist confirmation file must contain a JSON object")
    return payload


def load_finalist_confirmation_contract(
    repo_root: Path,
    parent: EvaluationContract,
) -> FinalistConfirmationContract:
    path = repo_root.resolve() / "data/evaluation/llm_finalist_confirmation.json"
    confirmation = FinalistConfirmationContract.model_validate(_load_json(path))
    if confirmation.parent_contract_fingerprint != contract_fingerprint(parent):
        raise ValueError("finalist confirmation does not match the frozen parent contract")

    parent_variants = {variant.id: variant for variant in parent.prompt_variants.variants}
    control = next(
        variant
        for variant in confirmation.variants
        if variant.id == confirmation.control_variant_id
    )
    frozen_control = parent_variants.get(confirmation.control_variant_id)
    if frozen_control is None or control.model_dump() != frozen_control.model_dump():
        raise ValueError("the finalist control must exactly reproduce the frozen baseline")
    if confirmation.source_candidate_id not in parent_variants:
        raise ValueError("source_candidate_id is not present in the frozen comparison")
    return confirmation


def finalist_contract_fingerprint(contract: FinalistConfirmationContract) -> str:
    canonical = json.dumps(
        contract.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def finalist_output_root(
    repo_root: Path,
    contract: FinalistConfirmationContract,
) -> Path:
    return (repo_root.resolve() / contract.outputs.root).resolve()
