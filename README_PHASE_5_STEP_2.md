# Phase 5 Step 2 — Controlled Function Tools

This increment adds a deterministic, side-effect-free function-tool layer.

## Scope

The new `ControlledToolRegistry` contains an explicit allowlist. It does not
perform dynamic imports, `eval`, shell execution, filesystem access, network
requests, database writes, or user-controlled function lookup.

The initial controlled tools are:

- `percentage_change`
- `weighted_score`

These tools support common Business Analysis, Project Management, prioritization,
variance, and option-assessment workflows.

## Safety contract

- Only registered tool names may execute.
- Inputs are validated with strict Pydantic models.
- Extra fields are rejected.
- Weighted-score item count is capped at 100.
- Tool failures return a controlled `ToolExecutionError`.
- Tool outputs are structured dictionaries.
- No route or LLM autonomously invokes tools in this step.

Later Phase 5 steps may selectively call these tools through explicit routing.
This increment establishes the execution boundary first.

## Files

- `pliris/tools/__init__.py`
- `pliris/tools/registry.py`
- `tests/unit/test_controlled_tools.py`
- `README_PHASE_5_STEP_2.md`

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit/test_controlled_tools.py -v
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected results:

```text
10 focused tests passed
129 non-integration tests passed, 13 deselected
13 integration tests passed, 129 deselected
```

The existing four Supabase deprecation warnings may remain.

## Review checkpoints

Confirm that:

- unknown tools fail closed;
- blank tool names fail closed;
- arbitrary shell or Python execution is impossible through the registry;
- extra arguments fail validation;
- tools have no side effects;
- all existing request classification, retrieval, generation, API, and
  persistence tests remain green.

## Commit

```bash
git add \
  README_PHASE_5_STEP_2.md \
  pliris/tools/__init__.py \
  pliris/tools/registry.py \
  tests/unit/test_controlled_tools.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add controlled function tools (refs #8)"
git push
```
