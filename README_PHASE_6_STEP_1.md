# Phase 6 Step 1 — Frozen LLM Evaluation Contract

This increment defines the evaluation contract for comparing final
LLM-generated answers. It does not repeat the completed retrieval benchmark.

## Scope

Step 1 adds:

- three versioned generation-prompt candidates;
- a frozen twelve-case generation benchmark;
- fixed model, generation, retrieval, scoring, threshold, and budget settings;
- deterministic output paths;
- strict cross-file validation and a stable contract fingerprint;
- ten unit tests.

It makes no paid LLM calls and does not modify the production chat route,
orchestrator, generator, prompts, database, or API schema.

## Prompt candidates

1. `production_baseline_v1`
   - Uses the current Phase 5 production instructions without additions.
2. `evidence_first_v1`
   - Tests explicit evidence planning and tighter claim-to-citation placement.
3. `decision_ready_v1`
   - Tests practitioner-oriented organization and decision-ready structure.

The candidates change one evaluation dimension at a time. Mode-specific
instructions from Phase 5 continue to apply before any evaluation-only
candidate addition.

## Frozen benchmark

The benchmark contains twelve cases:

- eight hosted-retrieval cases;
- three synthetic-context cases;
- one empty-context case.

All five production request modes are covered:

- `grounded_question`;
- `framework_comparison`;
- `scenario_analysis`;
- `deliverable_outline`;
- `source_conflict_review`.

The suite includes:

- definitions and prioritization;
- framework comparisons;
- conditional scenario analysis;
- deliverable outlines;
- a direct source contradiction;
- a scope difference that should not be treated as contradiction;
- partial evidence that must not be completed through invention;
- the exact insufficient-evidence contract.

Retrieval context must be obtained once per case and reused unchanged across
all prompt candidates.

## Frozen run contract

Primary comparison:

```text
12 cases × 3 variants × 1 repetition = 36 live calls
```

Optional finalist confirmation:

```text
12 cases × 2 finalists × 1 additional repetition = 24 live calls
```

Maximum Phase 6 allowance:

```text
60 live calls
750,000 input tokens
144,000 output tokens
USD 10 estimated-cost ceiling
```

Step 2 must require runtime pricing rates and stop before exceeding any budget.

Quality dimensions use a 0–4 scale:

- groundedness: 25%;
- citation quality: 20%;
- mode fulfillment: 20%;
- completeness: 15%;
- relevance and clarity: 10%;
- uncertainty handling: 10%.

The configuration requires:

- automated weighted score of at least 3.2;
- human weighted score of at least 3.2;
- no unknown citations;
- citation validation;
- exact insufficient-evidence handling;
- critical failure rate no greater than 5%.

These thresholds are selection gates, not proof that one aggregate score alone
determines the production prompt.

## Files

```text
README_PHASE_6_STEP_1.md
data/evaluation/llm_prompt_variants.json
data/evaluation/llm_generation_benchmark.json
data/evaluation/llm_evaluation_config.json
evaluation/llm_contract.py
tests/unit/test_llm_evaluation_contract.py
artifacts/llm_evaluation/.gitkeep
.gitignore
```

## Apply

From the repository root on `feature-llm-evaluation`:

```bash
uv run python \
  /path/to/Pliris_Phase_6_Step_1/apply_phase6_step1.py \
  --repo .
```

The script is idempotent. It copies the evaluation assets and adds the ignored
LLM-evaluation artifact directory without changing production code.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit/test_llm_evaluation_contract.py -v
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected results:

```text
10 focused tests passed
143 non-integration tests passed, 13 deselected
13 integration tests passed, 143 deselected
```

The four existing Supabase deprecation warnings may remain.

## Inspection commands

```bash
uv run python - <<'PY'
from pathlib import Path

from evaluation.llm_contract import (
    contract_fingerprint,
    load_evaluation_contract,
)

contract = load_evaluation_contract(Path.cwd())

print("cases:", len(contract.benchmark.cases))
print("variants:", len(contract.prompt_variants.variants))
print("primary calls:", contract.primary_live_calls)
print("maximum calls:", contract.maximum_live_calls)
print("fingerprint:", contract_fingerprint(contract))
print("output root:", contract.config.outputs.root)
PY
```

Expected structural values:

```text
cases: 12
variants: 3
primary calls: 36
maximum calls: 60
output root: artifacts/llm_evaluation/v1/gpt-5-mini
```

The fingerprint is deterministic but depends on the exact frozen JSON content.

## Review checkpoints

Confirm that:

- exactly one variant is the unchanged production baseline;
- all prompt candidates are evaluation-only;
- every production request mode is covered;
- retrieval, synthetic, and empty contexts are covered;
- source-conflict fixtures contain at least two sources;
- empty context requires the exact insufficient-evidence response;
- scoring weights total 1.0;
- primary and maximum call counts fit the configured budgets;
- output paths are safe and deterministic;
- no production module changed;
- no OpenAI request occurred.

## Commit

After all gates pass:

```bash
git add \
  .gitignore \
  README_PHASE_6_STEP_1.md \
  artifacts/llm_evaluation/.gitkeep \
  data/evaluation/llm_evaluation_config.json \
  data/evaluation/llm_generation_benchmark.json \
  data/evaluation/llm_prompt_variants.json \
  evaluation/llm_contract.py \
  tests/unit/test_llm_evaluation_contract.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: freeze LLM evaluation contract (refs #9)"
git push -u origin feature-llm-evaluation
```

Do not mark Step 1 complete until the commit is pushed and every gate has been
recorded on issue #9.
