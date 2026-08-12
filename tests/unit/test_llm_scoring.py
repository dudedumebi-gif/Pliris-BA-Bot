from __future__ import annotations

from pathlib import Path

from evaluation.llm_contract import load_evaluation_contract
from evaluation.llm_scoring import score_answer
from pliris.generation.context_assembler import ContextSource
from pliris.generation.grounded_models import (
    GroundedAnswer,
    ResponseUsage,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def contract():
    return load_evaluation_contract(REPO_ROOT)


def source(citation_id: str) -> ContextSource:
    return ContextSource(
        citation_id=citation_id,
        chunk_id=f"chunk-{citation_id}",
        title="Source",
        source="source",
        page_start=1,
        page_end=1,
        page_label="1",
        score=1.0,
        rank=int(citation_id[1:]),
        document_id="doc",
        metadata={},
    )


def answer(
    text: str,
    citation_ids=("S1",),
    *,
    insufficient=False,
) -> GroundedAnswer:
    return GroundedAnswer(
        answer=text,
        citation_ids=tuple(citation_ids),
        citations=tuple(source(item) for item in citation_ids),
        insufficient_evidence=insufficient,
        model="gpt-5-mini",
        response_id="resp",
        usage=ResponseUsage(
            input_tokens=100,
            output_tokens=30,
            total_tokens=130,
        ),
        metadata={},
    )


def score(case_id: str, generated: GroundedAnswer):
    active = contract()
    case = next(item for item in active.benchmark.cases if item.id == case_id)
    return score_answer(
        case,
        generated,
        dimensions=active.config.scoring_dimensions,
        pass_threshold=(active.config.thresholds.automated_weighted_score_min),
    )


def test_scores_grounded_answer_with_terms_and_citations() -> None:
    result = score(
        "grounded_traceability_definition",
        answer(
            "Requirements traceability records lineage and "
            "supports backward traceability and impact analysis [S1]."
        ),
    )

    assert result.groundedness == 4.0
    assert result.citation_quality == 4.0
    assert result.completeness == 4.0
    assert result.critical_failures == ()


def test_partial_evidence_numeric_claim_is_critical_failure() -> None:
    result = score(
        "grounded_partial_evidence",
        answer("The pilot reduced processing time by 25% [S1]."),
    )

    assert "unsupported_numeric_claim_in_partial_evidence_case" in result.critical_failures
    assert result.passed is False


def test_scope_difference_conflict_requires_distinction_and_sources() -> None:
    result = score(
        "conflict_approval_scope",
        answer(
            "The sources address different scope and are not a direct contradiction [S1] [S2].",
            ("S1", "S2"),
        ),
    )

    assert result.mode_fulfillment == 4.0
    assert result.critical_failures == ()


def test_exact_insufficient_evidence_receives_full_scores() -> None:
    active = contract()
    case = next(
        item for item in active.benchmark.cases if item.id == "insufficient_vendor_threshold"
    )
    generated = answer(
        case.expected_exact_answer or "",
        (),
        insufficient=True,
    )

    result = score_answer(
        case,
        generated,
        dimensions=active.config.scoring_dimensions,
        pass_threshold=(active.config.thresholds.automated_weighted_score_min),
    )

    assert result.weighted_score == 4.0
    assert result.passed is True
