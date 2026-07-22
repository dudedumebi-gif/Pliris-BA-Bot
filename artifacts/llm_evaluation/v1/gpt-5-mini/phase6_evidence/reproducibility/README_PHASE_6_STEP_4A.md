# Phase 6 Step 4A — Hardened Finalist Confirmation

Step 3 established a clear human-score leader but no frozen variant met the
maximum 5% critical-failure rate. This increment freezes a controlled
confirmation rather than adopting a failed candidate.

## Finalists

The confirmation compares:

- `production_baseline_v1` — unchanged control;
- `decision_ready_hardened_v1` — the Step 3 leader with two targeted changes:
  - atomic citation-token and `citation_ids` serialization instructions;
  - partial-evidence handling that reserves the global fallback for cases where
    no substantive part can be answered.

The original prompt comparison, raw outputs, human scores, fingerprints, and
production prompt remain unchanged.

## Confirmation design

- Same twelve frozen cases and contexts.
- One confirmation repetition.
- Twenty-four total attempts.
- Twenty-two expected paid calls because the empty-context case remains local.
- Existing 33 paid primary calls plus 22 projected calls equals 55, below the
  frozen maximum of 60.
- Errors are locked as first-run evidence, scored as zero, and counted as
  critical failures.
- Zero response-contract failures are allowed.
- Automated acceptance requires a mean score of at least 3.2 and a critical
  failure rate no greater than 5%.
- Passing the automated gate does not select a prompt; blinded human review is
  still mandatory.

## Files

```text
README_PHASE_6_STEP_4A.md
data/evaluation/llm_finalist_confirmation.json
evaluation/llm_finalist_contract.py
evaluation/llm_finalist_runner.py
scripts/confirm_llm_finalists.py
tests/unit/test_llm_finalist_confirmation.py
```

## Apply

```bash
uv run python \
  /c/dev/Pliris_Phase_6_Step_4A/apply_phase6_step4a.py \
  --repo .
```

Applying the package makes no external call and does not change production.

## Quality gates

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit/test_llm_finalist_confirmation.py -v
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused result: 16 tests passed.

## Plan without external calls

```bash
uv run python -m scripts.confirm_llm_finalists --plan
```

Expected core values:

```text
source_candidate: decision_ready_v1
planned_attempts: 24
expected_generation_api_calls: 22
existing_primary_generation_api_calls: 33
projected_total_generation_api_calls: 55
max_total_live_calls: 60
production_prompt_changed: False
external_calls: 0
```

## Commit before the paid run

```bash
git add \
  README_PHASE_6_STEP_4A.md \
  data/evaluation/llm_finalist_confirmation.json \
  evaluation/llm_finalist_contract.py \
  evaluation/llm_finalist_runner.py \
  scripts/confirm_llm_finalists.py \
  tests/unit/test_llm_finalist_confirmation.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add LLM finalist confirmation workflow (refs #9)"
git push
```

Do not add generated evaluation artifacts.

## Paid execution

Only after the implementation is committed and current official pricing has
been verified, run:

```bash
uv run python -m scripts.confirm_llm_finalists \
  --execute \
  --generation-input-price-per-million <CURRENT_INPUT_RATE> \
  --generation-output-price-per-million <CURRENT_OUTPUT_RATE>
```

Outputs are written under:

```text
artifacts/llm_evaluation/v1/gpt-5-mini/finalist_confirmation/
```

Step 4A does not select or deploy a production prompt. Step 4B will blind the
confirmation outputs, collect human scores, apply the frozen decision policy,
and write the production-prompt decision record.
