from __future__ import annotations

import pytest

from pliris.agents.request_classifier import (
    RequestClassifier,
    RequestMode,
)


def test_classifier_defaults_to_grounded_question() -> None:
    result = RequestClassifier().classify("What is requirements traceability?")

    assert result.mode is RequestMode.GROUNDED_QUESTION
    assert result.confidence == 0.60
    assert result.matched_rule == "default_grounded_question"


@pytest.mark.parametrize(
    "message",
    [
        "Compare the BABOK and PMBOK frameworks.",
        "What is the difference between Agile and Waterfall methodologies?",
    ],
)
def test_classifier_detects_framework_comparison(
    message: str,
) -> None:
    result = RequestClassifier().classify(message)

    assert result.mode is RequestMode.FRAMEWORK_COMPARISON
    assert result.confidence == 0.93


@pytest.mark.parametrize(
    "message",
    [
        "What if the integration vendor misses the release date?",
        "Perform an impact analysis for removing this requirement.",
    ],
)
def test_classifier_detects_scenario_analysis(
    message: str,
) -> None:
    result = RequestClassifier().classify(message)

    assert result.mode is RequestMode.SCENARIO_ANALYSIS
    assert result.confidence == 0.90


@pytest.mark.parametrize(
    "message",
    [
        "Create an outline for a business requirements document.",
        "Provide a project charter template.",
    ],
)
def test_classifier_detects_deliverable_outline(
    message: str,
) -> None:
    result = RequestClassifier().classify(message)

    assert result.mode is RequestMode.DELIVERABLE_OUTLINE
    assert result.confidence == 0.88


@pytest.mark.parametrize(
    "message",
    [
        "These two source documents contain conflicting requirements.",
        "Reconcile the evidence and identify the authoritative source.",
    ],
)
def test_classifier_detects_source_conflict_review(
    message: str,
) -> None:
    result = RequestClassifier().classify(message)

    assert result.mode is RequestMode.SOURCE_CONFLICT_REVIEW
    assert result.confidence == 0.96


def test_source_conflict_takes_priority_over_comparison() -> None:
    result = RequestClassifier().classify(
        "Compare the conflicting requirements in the two source documents."
    )

    assert result.mode is RequestMode.SOURCE_CONFLICT_REVIEW


def test_classifier_normalizes_case_and_whitespace() -> None:
    result = RequestClassifier().classify("  CREATE\nA   PROJECT CHARTER TEMPLATE  ")

    assert result.mode is RequestMode.DELIVERABLE_OUTLINE


def test_classification_serializes_to_api_ready_dict() -> None:
    payload = RequestClassifier().classify("Assess the impact if the API is unavailable.").to_dict()

    assert payload == {
        "mode": "scenario_analysis",
        "confidence": 0.90,
        "matched_rule": "scenario_analysis_language",
    }


def test_classifier_rejects_blank_message() -> None:
    with pytest.raises(ValueError, match="message must not be blank"):
        RequestClassifier().classify("   ")
