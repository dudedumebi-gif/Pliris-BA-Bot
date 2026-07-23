# Phase 7 Step 1F — Agentic Semantic Scope Router

## Why this replaces the regex patch

Business-analysis titles vary across organizations. Pliris must route based on
responsibilities, competencies, practices, artifacts, systems emphasis, and
user intent rather than maintain a catalogue of exact role names.

## Architecture

1. Existing deterministic safety guardrails run first.
2. `ScopeRouterAgent` uses the OpenAI Responses API with a strict Pydantic
   `ScopeDecision`.
3. The agent routes by semantic practice and intent.
4. A deterministic policy validates schema consistency and converts decisions
   below `SCOPE_CONFIDENCE_THRESHOLD` into an honest clarification.
5. Only clear, confident unrelated requests receive the exact out-of-scope
   response.
6. Retrieval and grounded generation remain responsible for evidence quality.

## Stable controls

The implementation fixes only stable controls in code: supported practice
domains, stable user intents, structured-output consistency, confidence
thresholds, safety, and operational failure handling. It does not hard-code a
list of organization-specific role titles.

## Hosted regression questions

- Who is a business analyst?
- Who is a business systems analyst?
- What differentiates a business analyst from a business systems analyst?
- Our organization calls the role a solution analyst. Is it within BA practice?
- What does an analyst do? (should request clarification)
- Is a cat an animal or a plant? (must remain out of scope)

## Structured-contract correction

`ScopeDecision.outcome` is the single source of truth for answer, clarify, or reject. Clarification is derived in application code rather than duplicated in a second model-generated boolean. The router also distinguishes scope ambiguity from missing facts needed to answer a clearly in-scope question.
