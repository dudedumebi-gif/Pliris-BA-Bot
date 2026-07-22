from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequestMode(StrEnum):
    GROUNDED_QUESTION = "grounded_question"
    FRAMEWORK_COMPARISON = "framework_comparison"
    SCENARIO_ANALYSIS = "scenario_analysis"
    DELIVERABLE_OUTLINE = "deliverable_outline"
    SOURCE_CONFLICT_REVIEW = "source_conflict_review"


class ContextStrategy(StrEnum):
    RETRIEVAL = "retrieval"
    SYNTHETIC = "synthetic"
    EMPTY = "empty"


class PageRange(StrictModel):
    start: int = Field(ge=1)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.end < self.start:
            raise ValueError("page range end must be greater than or equal to start")
        return self


class SyntheticChunk(StrictModel):
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    text: str = Field(min_length=1)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_pages(self) -> Self:
        if self.page_end < self.page_start:
            raise ValueError("synthetic chunk page_end must not precede page_start")
        return self


class EvaluationCase(StrictModel):
    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    request_mode: RequestMode
    context_strategy: ContextStrategy
    document_id: str | None = None
    retrieval_query: str | None = None
    expected_page_ranges: tuple[PageRange, ...] = ()
    required_term_groups: tuple[tuple[str, ...], ...] = ()
    minimum_term_groups: int = Field(default=0, ge=0)
    synthetic_chunks: tuple[SyntheticChunk, ...] = ()
    expected_behaviors: tuple[str, ...] = Field(min_length=1)
    forbidden_behaviors: tuple[str, ...] = Field(min_length=1)
    minimum_citations: int = Field(ge=0)
    expect_insufficient_evidence: bool
    expected_exact_answer: str | None = None
    tags: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_context_contract(self) -> Self:
        if self.context_strategy is ContextStrategy.RETRIEVAL:
            if not self.document_id:
                raise ValueError("retrieval cases require document_id")
            if self.synthetic_chunks:
                raise ValueError("retrieval cases cannot include synthetic_chunks")
            if not self.retrieval_query:
                raise ValueError("retrieval cases require retrieval_query")
            if not self.expected_page_ranges:
                raise ValueError("retrieval cases require expected_page_ranges")

        if self.context_strategy is ContextStrategy.SYNTHETIC:
            if not self.synthetic_chunks:
                raise ValueError("synthetic cases require synthetic_chunks")
            if self.document_id or self.retrieval_query:
                raise ValueError("synthetic cases cannot configure document_id or retrieval_query")

        if self.context_strategy is ContextStrategy.EMPTY:
            if self.document_id or self.retrieval_query or self.synthetic_chunks:
                raise ValueError("empty cases cannot configure a context source")
            if not self.expect_insufficient_evidence:
                raise ValueError("empty cases must expect the insufficient-evidence response")
            if self.minimum_citations != 0:
                raise ValueError("empty cases must require zero citations")
            if not self.expected_exact_answer:
                raise ValueError("empty cases require expected_exact_answer")

        if self.request_mode is RequestMode.SOURCE_CONFLICT_REVIEW and (
            self.context_strategy is not ContextStrategy.SYNTHETIC or len(self.synthetic_chunks) < 2
        ):
            raise ValueError("source-conflict cases require at least two synthetic chunks")

        if self.minimum_term_groups > len(self.required_term_groups):
            raise ValueError("minimum_term_groups cannot exceed required_term_groups")

        if self.context_strategy is not ContextStrategy.EMPTY and self.minimum_citations < 1:
            raise ValueError("non-empty cases must require at least one citation")

        return self


class GenerationBenchmark(StrictModel):
    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_suite(self) -> Self:
        case_ids = [case.id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("benchmark case ids must be unique")

        modes = {case.request_mode for case in self.cases}
        missing_modes = set(RequestMode) - modes
        if missing_modes:
            missing = ", ".join(sorted(mode.value for mode in missing_modes))
            raise ValueError(f"benchmark is missing request modes: {missing}")

        strategies = {case.context_strategy for case in self.cases}
        missing_strategies = set(ContextStrategy) - strategies
        if missing_strategies:
            missing = ", ".join(sorted(strategy.value for strategy in missing_strategies))
            raise ValueError(f"benchmark is missing context strategies: {missing}")

        return self


class PromptVariant(StrictModel):
    id: str = Field(min_length=1)
    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    additional_instructions: str
    is_production_baseline: bool


class PromptVariantSet(StrictModel):
    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    variants: tuple[PromptVariant, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_variants(self) -> Self:
        variant_ids = [variant.id for variant in self.variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("prompt variant ids must be unique")

        baselines = [variant for variant in self.variants if variant.is_production_baseline]
        if len(baselines) != 1:
            raise ValueError("exactly one production baseline is required")
        if baselines[0].additional_instructions.strip():
            raise ValueError("the production baseline must not add evaluation instructions")

        for variant in self.variants:
            if not variant.is_production_baseline and not variant.additional_instructions.strip():
                raise ValueError("non-baseline variants require additional instructions")

        return self


class GenerationSettings(StrictModel):
    max_output_tokens: int = Field(ge=100)
    reasoning_effort: str = Field(min_length=1)
    store: bool


class RetrievalSettings(StrictModel):
    top_k: int = Field(ge=1, le=20)
    reuse_context_across_variants: bool


class ScoringDimension(StrictModel):
    id: str = Field(min_length=1)
    weight: float = Field(gt=0, le=1)
    scale_min: int
    scale_max: int

    @model_validator(mode="after")
    def validate_scale(self) -> Self:
        if self.scale_max <= self.scale_min:
            raise ValueError("scoring scale_max must be greater than scale_min")
        return self


class PassThresholds(StrictModel):
    automated_weighted_score_min: float
    human_weighted_score_min: float
    critical_failure_rate_max: float = Field(ge=0, le=1)
    unknown_citation_count_max: int = Field(ge=0)
    citation_validation_required: bool
    exact_insufficient_evidence_required: bool


class EvaluationBudget(StrictModel):
    max_primary_live_calls: int = Field(ge=1)
    max_total_live_calls: int = Field(ge=1)
    max_total_input_tokens: int = Field(ge=1)
    max_total_output_tokens: int = Field(ge=1)
    max_estimated_cost_usd: float = Field(gt=0)
    stop_on_budget_exceeded: bool
    pricing_rates_source: str = Field(min_length=1)


class OutputPaths(StrictModel):
    root: str = Field(min_length=1)
    frozen_contexts_jsonl: str = Field(min_length=1)
    raw_outputs_jsonl: str = Field(min_length=1)
    automated_scores_csv: str = Field(min_length=1)
    automated_summary_json: str = Field(min_length=1)
    automated_summary_md: str = Field(min_length=1)
    blinded_review_csv: str = Field(min_length=1)
    blinding_key_json: str = Field(min_length=1)
    human_scores_csv: str = Field(min_length=1)
    decision_record_md: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_relative_paths(self) -> Self:
        for field_name, value in self.model_dump().items():
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{field_name} must be a safe relative path")
        return self


class EvaluationConfig(StrictModel):
    version: int = Field(ge=1)
    name: str = Field(min_length=1)
    benchmark_path: str = Field(min_length=1)
    prompt_variants_path: str = Field(min_length=1)
    variant_ids: tuple[str, ...] = Field(min_length=3)
    model: str = Field(min_length=1)
    generation: GenerationSettings
    retrieval: RetrievalSettings
    primary_repetitions: int = Field(ge=1)
    finalist_count: int = Field(ge=1)
    finalist_confirmation_repetitions: int = Field(ge=1)
    scoring_dimensions: tuple[ScoringDimension, ...] = Field(min_length=1)
    thresholds: PassThresholds
    budget: EvaluationBudget
    outputs: OutputPaths

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        if len(self.variant_ids) != len(set(self.variant_ids)):
            raise ValueError("variant_ids must be unique")

        dimension_ids = [dimension.id for dimension in self.scoring_dimensions]
        if len(dimension_ids) != len(set(dimension_ids)):
            raise ValueError("scoring dimension ids must be unique")

        total_weight = sum(dimension.weight for dimension in self.scoring_dimensions)
        if abs(total_weight - 1.0) > 1e-9:
            raise ValueError("scoring dimension weights must sum to 1.0")

        if self.finalist_count > len(self.variant_ids):
            raise ValueError("finalist_count cannot exceed variant count")

        if not self.retrieval.reuse_context_across_variants:
            raise ValueError("evaluation contexts must be reused across prompt variants")

        return self


class EvaluationContract(StrictModel):
    benchmark: GenerationBenchmark
    prompt_variants: PromptVariantSet
    config: EvaluationConfig

    @property
    def primary_live_calls(self) -> int:
        return (
            len(self.benchmark.cases)
            * len(self.config.variant_ids)
            * self.config.primary_repetitions
        )

    @property
    def finalist_confirmation_calls(self) -> int:
        return (
            len(self.benchmark.cases)
            * self.config.finalist_count
            * self.config.finalist_confirmation_repetitions
        )

    @property
    def maximum_live_calls(self) -> int:
        return self.primary_live_calls + self.finalist_confirmation_calls

    @model_validator(mode="after")
    def validate_cross_file_contract(self) -> Self:
        available_ids = {variant.id for variant in self.prompt_variants.variants}
        configured_ids = set(self.config.variant_ids)
        if configured_ids != available_ids:
            missing = available_ids - configured_ids
            unknown = configured_ids - available_ids
            raise ValueError(
                "configured prompt variants must exactly match the frozen set; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}"
            )

        if self.primary_live_calls > self.config.budget.max_primary_live_calls:
            raise ValueError("primary run exceeds max_primary_live_calls")

        if self.maximum_live_calls > self.config.budget.max_total_live_calls:
            raise ValueError("full evaluation exceeds max_total_live_calls")

        maximum_output_tokens = self.maximum_live_calls * self.config.generation.max_output_tokens
        if maximum_output_tokens > self.config.budget.max_total_output_tokens:
            raise ValueError("full evaluation exceeds max_total_output_tokens")

        return self


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"evaluation file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"evaluation file is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"evaluation file must contain a JSON object: {path}")
    return payload


def load_evaluation_contract(repo_root: Path) -> EvaluationContract:
    root = repo_root.resolve()
    config_path = root / "data/evaluation/llm_evaluation_config.json"
    config = EvaluationConfig.model_validate(_load_json(config_path))
    benchmark = GenerationBenchmark.model_validate(_load_json(root / config.benchmark_path))
    prompt_variants = PromptVariantSet.model_validate(
        _load_json(root / config.prompt_variants_path)
    )
    return EvaluationContract(
        benchmark=benchmark,
        prompt_variants=prompt_variants,
        config=config,
    )


def render_variant_instructions(
    base_instructions: str,
    variant: PromptVariant,
) -> str:
    normalized_base = base_instructions.strip()
    if not normalized_base:
        raise ValueError("base_instructions must not be blank")

    additional = variant.additional_instructions.strip()
    if not additional:
        return normalized_base
    return f"{normalized_base}\n\n{additional}"


def contract_fingerprint(contract: EvaluationContract) -> str:
    canonical = json.dumps(
        contract.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deterministic_output_root(
    repo_root: Path,
    contract: EvaluationContract,
) -> Path:
    return (repo_root.resolve() / contract.config.outputs.root).resolve()
