from __future__ import annotations

import re
from typing import Any

from pydantic import Field

from evaluation.llm_contract import (
    EvaluationCase,
    RequestMode,
    ScoringDimension,
    StrictModel,
)
from pliris.generation.grounded_models import GroundedAnswer

_CITATION_RE = re.compile(r"\[S[1-9]\d*\]")
_NUMERIC_CLAIM_RE = re.compile(
    r"(?:[$€£]\s*\d)|(?:\b\d+(?:\.\d+)?\s*%)",
    re.IGNORECASE,
)


class AutomatedEvaluation(StrictModel):
    groundedness: float = Field(ge=0, le=4)
    citation_quality: float = Field(ge=0, le=4)
    mode_fulfillment: float = Field(ge=0, le=4)
    completeness: float = Field(ge=0, le=4)
    relevance_clarity: float = Field(ge=0, le=4)
    uncertainty_handling: float = Field(ge=0, le=4)
    weighted_score: float = Field(ge=0, le=4)
    critical_failures: tuple[str, ...] = ()
    passed: bool
    checks: dict[str, Any] = Field(default_factory=dict)


def _normalized(text: str) -> str:
    return " ".join(text.lower().split())


def _term_group_matches(
    answer: str,
    groups: tuple[tuple[str, ...], ...],
) -> int:
    normalized = _normalized(answer)
    return sum(1 for group in groups if any(term.lower() in normalized for term in group))


def _citation_coverage(answer: str) -> float:
    candidates: list[str] = []
    for raw_line in answer.splitlines():
        line = raw_line.strip().lstrip("#-*0123456789. ").strip()
        if len(line) < 20 or line.endswith(":"):
            continue
        candidates.append(line)

    if not candidates:
        return 0.0
    cited = sum(1 for line in candidates if _CITATION_RE.search(line))
    return cited / len(candidates)


def _mode_score(
    case: EvaluationCase,
    answer: str,
    citation_count: int,
) -> tuple[float, dict[str, Any]]:
    normalized = _normalized(answer)
    checks: dict[str, Any] = {}

    if case.request_mode is RequestMode.GROUNDED_QUESTION:
        checks["direct_answer_present"] = len(normalized.split()) >= 8
        return (
            4.0 if checks["direct_answer_present"] else 2.0,
            checks,
        )

    if case.request_mode is RequestMode.FRAMEWORK_COMPARISON:
        comparison_signals = sum(
            signal in normalized
            for signal in (
                "similar",
                "differ",
                "whereas",
                "both",
                "comparison",
                "in contrast",
            )
        )
        checks["comparison_signal_count"] = comparison_signals
        checks["multiple_citations"] = citation_count >= 2
        score = min(
            4.0,
            comparison_signals * 1.5 + (1.0 if citation_count >= 2 else 0.0),
        )
        return score, checks

    if case.request_mode is RequestMode.SCENARIO_ANALYSIS:
        conditional = any(
            marker in normalized for marker in ("if ", " may ", " could ", " would ", "depends")
        )
        uncertainty = any(
            marker in normalized
            for marker in (
                "assumption",
                "uncertain",
                "evidence gap",
                "not established",
                "additional evidence",
            )
        )
        checks["conditional_language"] = conditional
        checks["uncertainty_language"] = uncertainty
        return (
            (2.0 if conditional else 0.0) + (2.0 if uncertainty else 0.0),
            checks,
        )

    if case.request_mode is RequestMode.DELIVERABLE_OUTLINE:
        structured = "\n-" in answer or "\n1." in answer or "\n##" in answer
        outline_signals = sum(
            signal in normalized
            for signal in (
                "purpose",
                "audience",
                "section",
                "input",
                "review",
                "placeholder",
                "evidence gap",
            )
        )
        checks["structured_outline"] = structured
        checks["outline_signal_count"] = outline_signals
        return min(
            4.0,
            (2.0 if structured else 0.0) + min(2.0, outline_signals / 2),
        ), checks

    all_sources = citation_count >= case.minimum_citations
    conflict_language = any(
        marker in normalized
        for marker in (
            "conflict",
            "contradiction",
            "unresolved",
            "different scope",
            "do not conflict",
            "not a direct contradiction",
        )
    )
    if "scope-difference" in case.tags:
        distinction = "scope" in normalized and any(
            marker in normalized
            for marker in (
                "different",
                "do not conflict",
                "not a direct contradiction",
                "distinct",
            )
        )
    else:
        distinction = any(
            marker in normalized for marker in ("conflict", "contradiction", "unresolved")
        )
    checks["all_required_sources_cited"] = all_sources
    checks["conflict_language"] = conflict_language
    checks["required_distinction"] = distinction
    return (
        (1.5 if all_sources else 0.0)
        + (1.0 if conflict_language else 0.0)
        + (1.5 if distinction else 0.0),
        checks,
    )


def _relevance_clarity_score(answer: str) -> float:
    word_count = len(answer.split())
    if 15 <= word_count <= 700:
        return 4.0
    if 701 <= word_count <= 900:
        return 3.0
    if 901 <= word_count <= 1_200:
        return 2.0
    return 1.0


def _uncertainty_score(
    case: EvaluationCase,
    answer: str,
) -> float:
    normalized = _normalized(answer)
    requires_uncertainty = (
        case.request_mode
        in {
            RequestMode.SCENARIO_ANALYSIS,
            RequestMode.SOURCE_CONFLICT_REVIEW,
        }
        or "partial-evidence" in case.tags
        or case.expect_insufficient_evidence
    )
    if not requires_uncertainty:
        return 4.0

    markers = (
        "insufficient",
        "not established",
        "not measured",
        "unknown",
        "uncertain",
        "assumption",
        "depends",
        "unresolved",
        "additional evidence",
        "evidence gap",
        "cannot determine",
    )
    count = sum(marker in normalized for marker in markers)
    if count >= 2:
        return 4.0
    if count == 1:
        return 3.0
    return 0.0


def _weighted_score(
    scores: dict[str, float],
    dimensions: tuple[ScoringDimension, ...],
) -> float:
    return round(
        sum(scores[dimension.id] * dimension.weight for dimension in dimensions),
        4,
    )


def score_answer(
    case: EvaluationCase,
    answer: GroundedAnswer,
    *,
    dimensions: tuple[ScoringDimension, ...],
    pass_threshold: float,
) -> AutomatedEvaluation:
    critical_failures: list[str] = []
    checks: dict[str, Any] = {}
    answer_text = answer.answer.strip()
    citation_count = len(answer.citation_ids)

    if case.expect_insufficient_evidence:
        exact = (
            answer.insufficient_evidence
            and answer_text == case.expected_exact_answer
            and citation_count == 0
        )
        checks["exact_insufficient_evidence"] = exact
        if not exact:
            critical_failures.append("incorrect_insufficient_evidence_response")
        base_score = 4.0 if exact else 0.0
        scores = {
            "groundedness": base_score,
            "citation_quality": base_score,
            "mode_fulfillment": base_score,
            "completeness": base_score,
            "relevance_clarity": base_score,
            "uncertainty_handling": base_score,
        }
    else:
        if answer.insufficient_evidence:
            critical_failures.append("unexpected_insufficient_evidence_response")
        if citation_count < case.minimum_citations:
            critical_failures.append("minimum_citations_not_met")

        available_ids = {source.citation_id for source in answer.citations}
        unknown_ids = sorted(set(answer.citation_ids) - available_ids)
        checks["unknown_citation_ids"] = unknown_ids
        if unknown_ids:
            critical_failures.append("unknown_citation_ids")

        if "partial-evidence" in case.tags and _NUMERIC_CLAIM_RE.search(answer_text):
            critical_failures.append("unsupported_numeric_claim_in_partial_evidence_case")

        coverage = _citation_coverage(answer_text)
        checks["citation_coverage_ratio"] = round(coverage, 4)
        groundedness = round(coverage * 4, 4)

        citation_quality = (
            4.0 if citation_count >= case.minimum_citations and not unknown_ids else 0.0
        )
        mode_fulfillment, mode_checks = _mode_score(
            case,
            answer_text,
            citation_count,
        )
        checks.update(mode_checks)

        matched_groups = _term_group_matches(
            answer_text,
            case.required_term_groups,
        )
        checks["matched_answer_term_groups"] = matched_groups
        if case.minimum_term_groups == 0:
            completeness = 4.0 if len(answer_text.split()) >= 8 else 2.0
        elif matched_groups >= case.minimum_term_groups:
            completeness = 4.0
        elif matched_groups == max(0, case.minimum_term_groups - 1):
            completeness = 3.0
        elif matched_groups > 0:
            completeness = 2.0
        else:
            completeness = 0.0

        scores = {
            "groundedness": groundedness,
            "citation_quality": citation_quality,
            "mode_fulfillment": round(mode_fulfillment, 4),
            "completeness": completeness,
            "relevance_clarity": _relevance_clarity_score(answer_text),
            "uncertainty_handling": _uncertainty_score(
                case,
                answer_text,
            ),
        }

    weighted_score = _weighted_score(scores, dimensions)
    passed = not critical_failures and weighted_score >= pass_threshold
    return AutomatedEvaluation(
        groundedness=scores["groundedness"],
        citation_quality=scores["citation_quality"],
        mode_fulfillment=scores["mode_fulfillment"],
        completeness=scores["completeness"],
        relevance_clarity=scores["relevance_clarity"],
        uncertainty_handling=scores["uncertainty_handling"],
        weighted_score=weighted_score,
        critical_failures=tuple(critical_failures),
        passed=passed,
        checks=checks,
    )
