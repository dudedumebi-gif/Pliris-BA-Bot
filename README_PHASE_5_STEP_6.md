# Phase 5 Step 6 — Grounded Source-Conflict Review

This final Phase 5 increment activates the `source_conflict_review` request
mode inside the existing grounded response pipeline.

## Behaviour

The route and orchestrator already propagate `request_mode`. Step 6 adds a
source-conflict review instruction profile to `GroundedResponseGenerator`.

For source-conflict requests, Pliris should make disagreements visible rather
than blending them into a single unsupported conclusion.

When supported by the retrieved evidence, the response should identify:

- the exact claim, recommendation, rule, or decision point in dispute;
- each source's position, presented separately with its own citations;
- points of agreement between the sources;
- whether the difference appears to be a direct contradiction or may result
  from different scope, terminology, dates, versions, methods, assumptions, or
  contexts;
- source authority, recency, or applicability only when the retrieved context
  provides evidence for that comparison;
- the practical impact of leaving the conflict unresolved;
- the additional evidence or validation needed to resolve it.

## Guardrails

The conflict-review profile must:

- cite each source's position independently;
- avoid merging incompatible claims into a false consensus;
- avoid omitting a supported minority or alternative position;
- avoid selecting a winner or ranking sources without evidence;
- avoid inferring chronology, authority, applicability, or supersession when
  the context does not establish it;
- state explicitly when the available evidence cannot resolve the conflict.

A conflict can be explained without being resolved. When the knowledge base
contains enough evidence to describe the disagreement but not settle it,
Pliris should report the conflict as unresolved rather than fabricate a
definitive answer.

## Preserved contracts

- prompt-injection detection remains first;
- scope classification remains before request-mode classification;
- the exact out-of-scope response is unchanged;
- retrieval remains hosted Hybrid search;
- generation remains context-only;
- all substantive factual claims require validated inline citations;
- insufficient-evidence handling remains unchanged;
- persistence remains unchanged;
- controlled tools are not invoked;
- no database migration or additional OpenAI request is introduced.

## Apply

From the repository root on `feature-agentic-behaviour`:

```bash
uv run python \
  /path/to/Pliris_Phase_5_Step_6/apply_phase5_step6.py \
  --repo .
```

The script is idempotent and stops when the expected Step 5 anchors are absent.

## Files changed

- `README_PHASE_5_STEP_6.md`
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
28 focused tests passed
133 non-integration tests passed, 13 deselected
13 integration tests passed, 133 deselected
```

The four existing Supabase deprecation warnings may remain.

## Review checkpoints

Confirm that:

- `source_conflict_review` adds only the source-conflict profile;
- framework comparison, scenario analysis, and deliverable outline remain
  isolated;
- ordinary grounded questions retain only the base instructions;
- each conflicting position is kept separate and independently cited;
- unsupported source ranking, authority, chronology, or supersession is
  prohibited;
- unresolved conflicts remain explicitly unresolved;
- retrieval, citations, insufficient-evidence handling, persistence, and tool
  boundaries remain unchanged.

## Commit

After every quality gate passes:

```bash
git add \
  README_PHASE_5_STEP_6.md \
  pliris/generation/grounded_generator.py \
  tests/unit/test_grounded_generator.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add grounded source conflict review (refs #8)"
git push
```

Do not close issue #8 until the commit is pushed and the final Phase 5
verification results are recorded.
