from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class RequestMode(StrEnum):
    """Supported agentic request modes."""

    GROUNDED_QUESTION = "grounded_question"
    FRAMEWORK_COMPARISON = "framework_comparison"
    SCENARIO_ANALYSIS = "scenario_analysis"
    DELIVERABLE_OUTLINE = "deliverable_outline"
    SOURCE_CONFLICT_REVIEW = "source_conflict_review"


@dataclass(frozen=True, slots=True)
class RequestClassification:
    """Deterministic request-mode classification result."""

    mode: RequestMode
    confidence: float
    matched_rule: str

    def to_dict(self) -> dict[str, str | float]:
        """Return an API-ready representation."""

        return {
            "mode": self.mode.value,
            "confidence": self.confidence,
            "matched_rule": self.matched_rule,
        }


@dataclass(frozen=True, slots=True)
class _ClassificationRule:
    mode: RequestMode
    confidence: float
    name: str
    patterns: tuple[re.Pattern[str], ...]

    def matches(self, message: str) -> bool:
        return any(pattern.search(message) for pattern in self.patterns)


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


_RULES: Final[tuple[_ClassificationRule, ...]] = (
    _ClassificationRule(
        mode=RequestMode.SOURCE_CONFLICT_REVIEW,
        confidence=0.96,
        name="source_conflict_language",
        patterns=_compile(
            (
                r"\b(?:conflict(?:ing)?|contradict(?:ion|ory|s)?|"
                r"discrepanc(?:y|ies)|inconsisten(?:t|cy|cies))\b"
                r".*\b(?:source|document|evidence|requirement|record)s?\b"
            ),
            (
                r"\b(?:source|document|evidence|requirement|record)s?\b"
                r".*\b(?:conflict(?:ing)?|contradict(?:ion|ory|s)?|"
                r"discrepanc(?:y|ies)|inconsisten(?:t|cy|cies))\b"
            ),
            r"\breconcile (?:the )?(?:sources|documents|evidence)\b",
            (
                r"\bwhich source (?:is|should be) "
                r"(?:authoritative|trusted|used)\b"
            ),
        ),
    ),
    _ClassificationRule(
        mode=RequestMode.FRAMEWORK_COMPARISON,
        confidence=0.93,
        name="framework_comparison_language",
        patterns=_compile(
            (
                r"\b(?:compare|contrast)\b.*\b(?:framework|methodology|"
                r"approach|technique|babok|pmbok|scrum|kanban|agile|"
                r"waterfall)s?\b"
            ),
            (
                r"\b(?:framework|methodology|approach|technique|babok|"
                r"pmbok|scrum|kanban|agile|waterfall)s?\b.*"
                r"\b(?:versus|vs\.?|difference between)\b"
            ),
            (
                r"\bdifference between\b.*\b(?:framework|methodology|"
                r"approach|technique|babok|pmbok|scrum|kanban|agile|"
                r"waterfall)s?\b"
            ),
        ),
    ),
    _ClassificationRule(
        mode=RequestMode.SCENARIO_ANALYSIS,
        confidence=0.90,
        name="scenario_analysis_language",
        patterns=_compile(
            r"\bwhat if\b",
            r"\bscenario(?: analysis)?\b",
            r"\bimpact analysis\b",
            r"\b(?:assess|evaluate) (?:the )?(?:impact|consequences|options)\b",
            r"\b(?:trade[- ]?off|option|decision) analysis\b",
        ),
    ),
    _ClassificationRule(
        mode=RequestMode.DELIVERABLE_OUTLINE,
        confidence=0.88,
        name="deliverable_outline_language",
        patterns=_compile(
            (
                r"\b(?:outline|template|structure|checklist)\b.*"
                r"\b(?:brd|business requirements document|business case|"
                r"project charter|requirements traceability matrix|rtm|"
                r"requirements document|stakeholder plan|risk register|"
                r"use case|user stor(?:y|ies)|acceptance criteria|"
                r"deliverable)\b"
            ),
            (
                r"\b(?:create|draft|build|prepare|develop|generate|provide)\b"
                r".*\b(?:outline|template|structure|checklist|brd|"
                r"business requirements document|business case|"
                r"project charter|requirements traceability matrix|rtm|"
                r"requirements document|stakeholder plan|risk register|"
                r"use case|user stor(?:y|ies)|acceptance criteria)\b"
            ),
        ),
    ),
)


class RequestClassifier:
    """Classify approved in-scope requests into agentic modes."""

    def classify(self, message: str) -> RequestClassification:
        """Return a deterministic request-mode classification."""

        normalized = " ".join(message.casefold().split())
        if not normalized:
            raise ValueError("message must not be blank")

        for rule in _RULES:
            if rule.matches(normalized):
                return RequestClassification(
                    mode=rule.mode,
                    confidence=rule.confidence,
                    matched_rule=rule.name,
                )

        return RequestClassification(
            mode=RequestMode.GROUNDED_QUESTION,
            confidence=0.60,
            matched_rule="default_grounded_question",
        )
