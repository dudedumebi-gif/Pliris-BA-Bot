# Phase 6 Step 3 — Blinded Human Review

This increment creates the offline blinded-review stage from the original 36
Phase 6 primary attempts. It makes no retrieval, embedding, or generation calls
and does not select a production prompt.

## What it does

- deterministically assigns Answer A/B/C per case;
- removes variant identities from reviewer-facing files;
- preserves the exact frozen context and accepted answer text;
- explicitly represents all six Step 2 citation-contract failures;
- locks failed responses to zero scores and critical-failure status;
- collects 0–4 scores across all six frozen dimensions;
- validates completeness, identities, fingerprints, and source-file hashes;
- reveals variant identities only after all scores are complete;
- generates an unblinded aggregate summary for Step 4.

## Apply

```bash
uv run python \
  /c/dev/Pliris_Phase_6_Step_3/apply_phase6_step3.py \
  --repo .
```

No external call is made.

## Quality gates

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit/test_llm_human_review.py -v
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused result: 19 tests passed.

## Prepare the blinded package

```bash
uv run python -m scripts.review_llm_prompts --prepare
```

Expected:

```text
attempts: 36
accepted_responses: 30
contract_failures: 6
external_calls: 0
```

Generated ignored artifacts:

```text
artifacts/llm_evaluation/v1/gpt-5-mini/human_review/
├── blinded_responses.csv
├── blinding_key.json
├── review_instructions.md
├── review_manifest.json
└── scores.csv
```

Do not open `blinding_key.json` until scoring is complete.

## Review

Use `review_instructions.md`, `blinded_responses.csv`, and `scores.csv`.
Score accepted responses from 0 to 4 for groundedness, citation quality, mode
fulfillment, completeness, relevance/clarity, and uncertainty handling.

Leave `contract_failure` rows unchanged. They are locked evidence from Step 2.

## Finalize

```bash
uv run python -m scripts.review_llm_prompts \
  --finalize \
  --reviewer-id "Dums"
```

This creates `human_review/summary.json` and `human_review/summary.md` only after
all 36 rows pass validation. Step 3 still does not select a production prompt.

## Commit

```bash
git add \
  README_PHASE_6_STEP_3.md \
  evaluation/llm_human_review.py \
  scripts/review_llm_prompts.py \
  tests/unit/test_llm_human_review.py

git commit -m "feat: add blinded LLM human review (refs #9)"
git push
```

Do not add generated files under `artifacts/llm_evaluation/`.
