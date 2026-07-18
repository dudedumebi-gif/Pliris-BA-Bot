# Phase 5 Step 4 — Grounded Scenario Analysis

This increment activates the `scenario_analysis` request mode inside the
existing grounded response pipeline.

## Behaviour

The route and orchestrator already propagate `request_mode`, so Step 4 adds a
scenario-analysis instruction profile to `GroundedResponseGenerator`.

For scenario-analysis requests, the model is instructed to distinguish:

- evidence-backed facts;
- user-supplied assumptions;
- conditional impacts that follow only if the scenario occurs;
- uncertainties and missing evidence.

When supported by the retrieved context, the response should cover:

- the scenario and material assumptions;
- affected areas and stakeholders;
- dependencies and constraints;
- likely impacts;
- risks and opportunities;
- response options and trade-offs;
- mitigations and decision considerations;
- evidence gaps.

## Guardrails

The scenario profile must not:

- present a hypothetical outcome as an established fact;
- assign unsupported probabilities or confidence levels;
- invent impacts, dependencies, stakeholders, or mitigations;
- declare a preferred option unless the evidence supports it;
- conceal uncertainty or missing evidence.

All existing grounded-generation contracts remain active.

## Preserved contracts

- prompt-injection detection remains first;
- scope classification remains before request-mode classification;
- the exact out-of-scope response is unchanged;
- retrieval remains hosted Hybrid search;
- generation remains context-only;
- substantive factual claims require validated inline citations;
- insufficient-evidence handling remains unchanged;
- persistence remains unchanged;
- controlled tools are not invoked;
- no database migration or additional OpenAI request is introduced.

## Apply

From the repository root on `feature-agentic-behaviour`:

```bash
uv run python \
  /path/to/Pliris_Phase_5_Step_4/apply_phase5_step4.py \
  --repo .
```

The script is idempotent and stops when the expected Step 3 anchors are absent.

## Files changed

- `README_PHASE_5_STEP_4.md`
- `pliris/generation/grounded_generator.py`
- `tests/unit/test_grounded_generator.py`

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_chat_route.py \
  tests/unit/test_grounded_generator.py \
  tests/unit/test_grounded_orchestrator.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected results:

```text
26 focused tests passed
131 non-integration tests passed, 13 deselected
13 integration tests passed, 131 deselected
```

The four existing Supabase deprecation warnings may remain.

## Review checkpoints

Confirm that:

- `scenario_analysis` adds the scenario-specific instruction profile;
- `framework_comparison` still adds only its own profile;
- ordinary grounded questions retain only the base instructions;
- hypothetical consequences remain explicitly conditional;
- unsupported probabilities and recommendations are prohibited;
- retrieval, citations, insufficient-evidence handling, persistence, and tool
  boundaries remain unchanged.

## Commit

```bash
git add \
  README_PHASE_5_STEP_4.md \
  pliris/generation/grounded_generator.py \
  tests/unit/test_grounded_generator.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add grounded scenario analysis mode (refs #8)"
git push
```
