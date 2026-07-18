# Phase 6 Step 2 — Live Prompt Comparison and Automated Scoring

This increment adds the live evaluation runner for the frozen Phase 6 contract.

It does not change the production chat route, orchestrator, generator, prompt
selection, database, or API schema.

## Safety model

Applying and testing this increment performs no hosted retrieval, embedding, or
generation call.

External calls require an explicit command:

1. `--prepare-contexts`
   - invokes hosted Hybrid retrieval for the eight retrieval-backed cases;
   - makes one embedding request per retrieval query through the production
     retriever;
   - freezes the resulting contexts for reuse across every prompt variant.
2. `--execute`
   - requires the frozen context file to exist;
   - runs the three prompt candidates against the exact same context for each
     case;
   - skips the paid generation API for the empty-context case.

The runner never prepares contexts automatically during `--execute`.

## Components

```text
evaluation/llm_contexts.py
evaluation/llm_variant_generator.py
evaluation/llm_scoring.py
evaluation/llm_runner.py
scripts/evaluate_llm_prompts.py
tests/unit/test_llm_contexts.py
tests/unit/test_llm_variant_generator.py
tests/unit/test_llm_scoring.py
tests/unit/test_llm_runner.py
README_PHASE_6_STEP_2.md
```

### Frozen contexts

The context freezer:

- runs each retrieval-backed benchmark query once;
- uses production `HostedHybridRetriever`;
- converts synthetic fixtures through the normal `ContextAssembler`;
- preserves the empty-context fallback;
- requires page overlap and minimum concept coverage for retrieval cases;
- stores original normalized chunks and assembled citation sources;
- fingerprints every context;
- records actual embedding input tokens;
- writes atomically to the ignored artifact directory.

Any failed context-quality gate stops the workflow before generation.

### Prompt comparison

The evaluation-only generator:

- retains the production mode-specific prompt;
- appends only the selected evaluation candidate instructions;
- uses the production structured response schema;
- uses the production citation validator;
- preserves exact insufficient-evidence behavior;
- records raw JSON output, validated answer, citations, usage, latency, model,
  response ID, and failures;
- does not persist evaluation conversations to the application database.

The baseline candidate adds no instructions.

### Run order

The runner rotates candidate order by case:

```text
Case 1: A, B, C
Case 2: B, C, A
Case 3: C, A, B
```

This deterministic counterbalancing reduces simple ordering bias.

The primary plan contains 36 attempts. The empty-context case is evaluated
locally for all three variants, so the expected number of paid generation API
calls is 33.

### Budget enforcement

Current prices are never hard-coded. Commands must supply runtime prices per
one million tokens for:

- generation input;
- generation output;
- embedding input.

The runner checks the frozen call, token, and USD ceilings before each paid
generation request. Missing usage is conservatively recorded from estimates.
A failed API attempt is also conservatively budgeted because it may still have
incurred usage.

### Automated scoring

Step 2 uses deterministic structural checks for:

- citation coverage and integrity;
- minimum citations;
- required concept coverage;
- request-mode signals;
- exact insufficient-evidence behavior;
- uncertainty language where required;
- unsupported numeric claims in the partial-evidence case;
- length and clarity bounds.

Reports include dimension scores, weighted score, critical failures, token
usage, latency, and estimated cost.

These checks do not establish semantic correctness. Step 3 remains the blinded
human review. Step 2 does not select a production prompt.

## Apply

Extract the package, then run from the repository root on
`feature-llm-evaluation`:

```bash
uv run python \
  /c/dev/Pliris_Phase_6_Step_2/apply_phase6_step2.py \
  --repo .
```

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_llm_contexts.py \
  tests/unit/test_llm_variant_generator.py \
  tests/unit/test_llm_scoring.py \
  tests/unit/test_llm_runner.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected results:

```text
18 focused tests passed
161 non-integration tests passed, 13 deselected
13 integration tests passed, 161 deselected
```

The four known Supabase deprecation warnings may remain.

## Inspect the no-call plan

```bash
uv run python -m scripts.evaluate_llm_prompts --plan
```

Expected structural output:

```text
cases: 12
variants: 3
planned_attempts: 36
expected_generation_api_calls: 33
external_calls: 0
```

## Context preparation

Do not use stale pricing values. Supply the current official embedding input
price at runtime:

```bash
uv run python -m scripts.evaluate_llm_prompts \
  --prepare-contexts \
  --embedding-input-price-per-million <CURRENT_RATE>
```

This writes:

```text
artifacts/llm_evaluation/v1/gpt-5-mini/frozen_contexts.jsonl
```

Review every printed context-quality row before generation. All twelve records
must show `passed=True`. Retrieval-backed records must have at least one
expected-page overlap and the configured minimum concept-group coverage.

Do not proceed to `--execute` when a context gate fails or retrieved evidence
is visibly unsuitable.

## Live primary comparison

After context review, supply current official prices:

```bash
uv run python -m scripts.evaluate_llm_prompts \
  --execute \
  --generation-input-price-per-million <CURRENT_INPUT_RATE> \
  --generation-output-price-per-million <CURRENT_OUTPUT_RATE>
```

The runner resumes successful attempts by default. Re-running the command does
not repeat successful calls.

Generated ignored artifacts:

```text
artifacts/llm_evaluation/v1/gpt-5-mini/
├── frozen_contexts.jsonl
└── primary/
    ├── raw_outputs.jsonl
    ├── automated_scores.csv
    ├── summary.json
    └── summary.md
```

Inspect:

```bash
cat artifacts/llm_evaluation/v1/gpt-5-mini/primary/summary.md
```

Also inspect all errors and critical failures in:

```text
primary/raw_outputs.jsonl
primary/automated_scores.csv
```

## Step 2 completion criteria

Step 2 remains open until:

- the runner and tests are committed and pushed;
- all twelve frozen contexts pass quality review;
- all 36 attempts are recorded;
- the expected 33 paid generation calls or documented resumptions complete;
- no budget is exceeded;
- raw outputs and failures are preserved;
- automated reports are generated and reviewed;
- no production prompt has been selected.

## Commit the runner

After the code and test gates pass:

```bash
git add \
  README_PHASE_6_STEP_2.md \
  evaluation/llm_contexts.py \
  evaluation/llm_runner.py \
  evaluation/llm_scoring.py \
  evaluation/llm_variant_generator.py \
  scripts/evaluate_llm_prompts.py \
  tests/unit/test_llm_contexts.py \
  tests/unit/test_llm_runner.py \
  tests/unit/test_llm_scoring.py \
  tests/unit/test_llm_variant_generator.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add LLM prompt comparison runner (refs #9)"
git push
```

Do not check off Step 2 merely because the runner is committed. The live
comparison and report review are part of the step.
