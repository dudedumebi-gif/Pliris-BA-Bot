# Phase 5 Step 1 — Deterministic Request Classification

This package adds the first Phase 5 agentic contract without executing tools
or changing the grounded response path.

## Behaviour

After prompt-injection and domain-scope checks, approved in-scope requests are
classified into one of five modes:

- `grounded_question`
- `framework_comparison`
- `scenario_analysis`
- `deliverable_outline`
- `source_conflict_review`

The classifier is deterministic and local. It does not make an additional
OpenAI request.

Step 1 exposes the classification through response metadata only. Every
in-scope request still uses the existing grounded orchestrator.

## Safety and compatibility

This increment preserves:

- the exact out-of-scope response;
- prompt-injection detection before all classification;
- no request-mode classification for blocked or out-of-scope requests;
- the hosted Hybrid retrieval path;
- grounded generation and citation validation;
- transactional persistence;
- copyright-safe public citation excerpts.

No database migration is included.

## Package contents

- `overlay/pliris/agents/request_classifier.py`
- `overlay/tests/unit/test_request_classifier.py`
- `apply_phase5_step1.py`

The apply script copies the new files and patches:

- `api/routes/chat.py`
- `tests/unit/test_chat_route.py`

## Apply

From the repository root on `feature-agentic-behaviour`:

```bash
uv run python /path/to/Pliris_Phase_5_Step_1/apply_phase5_step1.py --repo .
```

The script is idempotent. It stops rather than guessing when the expected
Phase 4 code anchors are absent.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_request_classifier.py \
  tests/unit/test_chat_route.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected results:

```text
22 focused tests passed
119 non-integration tests passed, 13 deselected
13 integration tests passed, 119 deselected
```

The four existing Supabase deprecation warnings may remain.

## Review checkpoints

Confirm that:

- an in-scope answer includes request-mode metadata;
- out-of-scope requests preserve the exact approved response;
- blocked and out-of-scope requests do not invoke the request classifier;
- the grounded orchestrator receives the same arguments as before;
- no tool or specialized mode executes in Step 1;
- all prior retrieval, generation, persistence, and API tests remain green.

## Commit

```bash
git add \
  README_PHASE_5_STEP_1.md \
  api/routes/chat.py \
  pliris/agents/request_classifier.py \
  tests/unit/test_chat_route.py \
  tests/unit/test_request_classifier.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add deterministic request classification (refs #8)"
git push
```
