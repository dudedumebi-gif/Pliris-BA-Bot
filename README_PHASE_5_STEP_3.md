# Phase 5 Step 3 — Grounded Framework Comparison

This increment activates the `framework_comparison` request mode inside the
existing grounded response pipeline.

## Behaviour

The request mode now travels through:

1. FastAPI chat route
2. `GroundedResponseOrchestrator`
3. `GroundedResponseGenerator`

Only `framework_comparison` receives an additional instruction profile. All
other current and future modes continue to use the base grounded instructions
until their own Phase 5 steps are implemented.

The comparison profile asks the model to cover, when supported by evidence:

- comparison basis;
- similarities;
- differences;
- suitable situations for each option;
- limitations and trade-offs;
- selection considerations.

It explicitly prohibits inventing missing comparison dimensions or declaring
an unsupported winner.

## Preserved contracts

- prompt-injection detection remains first;
- domain scope classification remains before request-mode classification;
- the exact out-of-scope response is unchanged;
- retrieval remains hosted Hybrid search;
- generation remains context-only;
- every substantive factual claim still requires validated inline citations;
- insufficient-evidence handling remains unchanged;
- transactional persistence remains enabled;
- no controlled function tool is invoked in this step;
- no database migration or additional OpenAI request is introduced.

## Apply

From the repository root on `feature-agentic-behaviour`:

```bash
uv run python \
  /path/to/Pliris_Phase_5_Step_3/apply_phase5_step3.py \
  --repo .
```

The script is idempotent and stops when the expected Step 2 anchors are absent.

## Files changed

- `README_PHASE_5_STEP_3.md`
- `api/routes/chat.py`
- `pliris/agents/grounded_orchestrator.py`
- `pliris/generation/grounded_generator.py`
- `tests/unit/test_chat_route.py`
- `tests/unit/test_grounded_generator.py`
- `tests/unit/test_grounded_orchestrator.py`

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
25 focused tests passed
130 non-integration tests passed, 13 deselected
13 integration tests passed, 130 deselected
```

The four existing Supabase deprecation warnings may remain.

## Review checkpoints

Confirm that:

- the route passes the classified request mode into the orchestrator;
- the orchestrator passes it into grounded generation;
- framework comparison adds the comparison instruction profile;
- ordinary grounded questions retain only the base instructions;
- unsupported comparison dimensions must not be invented;
- request mode is included in pipeline and persistence metadata;
- no tool executes;
- all guardrail, retrieval, citation, API, and persistence tests remain green.

## Commit

```bash
git add \
  README_PHASE_5_STEP_3.md \
  api/routes/chat.py \
  pliris/agents/grounded_orchestrator.py \
  pliris/generation/grounded_generator.py \
  tests/unit/test_chat_route.py \
  tests/unit/test_grounded_generator.py \
  tests/unit/test_grounded_orchestrator.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add grounded framework comparison mode (refs #8)"
git push
```
