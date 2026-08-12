from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ScopeOutcome(StrEnum):
    """Supported semantic routing outcomes."""

    IN_SCOPE = "in_scope"
    CLARIFICATION = "clarification"
    OUT_OF_SCOPE = "out_of_scope"


class ScopeCategory(StrEnum):
    """Stable practice domains understood by Pliris."""

    BUSINESS_ANALYSIS = "business_analysis"
    BUSINESS_SYSTEMS_ANALYSIS = "business_systems_analysis"
    PROJECT_MANAGEMENT = "project_management"
    FINANCIAL = "financial"
    AMBIGUOUS = "ambiguous"
    OUT_OF_SCOPE = "out_of_scope"


class ScopeIntent(StrEnum):
    """Stable user intents independent of organization-specific job titles."""

    ROLE_DEFINITION = "role_definition"
    ROLE_COMPARISON = "role_comparison"
    PRACTICE_BOUNDARY = "practice_boundary"
    COMPETENCY_OR_CAREER = "competency_or_career"
    REQUIREMENTS_OR_PROCESS = "requirements_or_process"
    SYSTEMS_OR_INTEGRATION = "systems_or_integration"
    ARTIFACT_OR_TECHNIQUE = "artifact_or_technique"
    PROJECT_DELIVERY = "project_delivery"
    FINANCIAL_ANALYSIS = "financial_analysis"
    OTHER_IN_SCOPE = "other_in_scope"
    AMBIGUOUS = "ambiguous"
    UNRELATED = "unrelated"


class ScopeDecision(BaseModel):
    """Typed decision returned by the semantic Scope Router Agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ScopeOutcome = Field(
        description="Whether Pliris should answer, clarify, or reject the query."
    )
    category: ScopeCategory = Field(description="The primary Pliris practice domain for the query.")
    intent: ScopeIntent = Field(
        description="The stable semantic intent, not an organization-specific title."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the complete routing decision.",
    )
    rationale: str = Field(
        min_length=1,
        max_length=500,
        description="A brief routing reason that does not answer the user.",
    )
