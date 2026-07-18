# Phase 5 Step 5 — Grounded Deliverable Outline

This increment activates the `deliverable_outline` request mode inside the
existing grounded response pipeline.

## Behaviour

The route and orchestrator already propagate `request_mode`. Step 5 adds a
deliverable-outline instruction profile to `GroundedResponseGenerator`.

For deliverable-outline requests, Pliris should provide a practical structure
for the requested BA, BSA, PM, or delivery artifact while remaining grounded
in the retrieved evidence.

When supported by the knowledge-base context and user request, the outline
should identify:

- the deliverable purpose and intended audience;
- recommended sections in a logical order;
- the expected content or question each section should address;
- required source inputs and supporting evidence;
- assumptions, dependencies, constraints, and exclusions;
- review, validation, approval, or sign-off checkpoints;
- traceability or quality checks;
- unresolved questions and evidence gaps.

## Guardrails

The deliverable profile must:

- distinguish evidence-backed requirements from suggested placeholders;
- preserve constraints explicitly supplied by the user;
- avoid claiming an outline is mandatory or standard unless evidence supports
  that claim;
- avoid fabricating names, owners, dates, figures, decisions, approvals,
  statuses, or completed analysis;
- avoid presenting the outline as a finished deliverable;
- state when evidence is insufficient for a requested section or detail.

All substantive factual claims remain subject to validated inline citations.

## Preserved contracts

- prompt-injection detection remains first;
- scope classification remains before request-mode classification;
- the exact out-of-scope response is unchanged;
- retrieval remains hosted Hybrid search;
- generation remains context-only;
- insufficient-evidence handling remains unchanged;
- persistence remains unchanged;
- controlled tools are not invoked;
- no database migration or additional OpenAI request is introduced.

## Apply

From the repository root on `feature-agentic-behaviour`:

```bash
uv run python \
  /path/to/Pliris_Phase_5_Step_5/apply_phase5_step5.py \
  --repo .
```

The script is idempotent and stops when the expected Step 4 anchors are absent.

## Files changed

- `README_PHASE_5_STEP_5.md`
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
27 focused tests passed
132 non-integration tests passed, 13 deselected
13 integration tests passed, 132 deselected
```

The four existing Supabase deprecation warnings may remain.

## Review checkpoints

Confirm that:

- `deliverable_outline` adds only the deliverable-outline profile;
- framework-comparison and scenario-analysis profiles remain isolated;
- ordinary grounded questions retain only the base instructions;
- the outline distinguishes evidence-backed content from placeholders;
- unsupported names, owners, dates, figures, approvals, and decisions are
  prohibited;
- the response does not masquerade as a completed deliverable;
- retrieval, citations, insufficient-evidence handling, persistence, and tool
  boundaries remain unchanged.

## Commit

```bash
git add \
  README_PHASE_5_STEP_5.md \
  pliris/generation/grounded_generator.py \
  tests/unit/test_grounded_generator.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add grounded deliverable outline mode (refs #8)"
git push
```
