# Phase 6 Step 4B — Blinded Finalist Diagnostic Review

Step 4A completed all 24 first-run finalist attempts, but neither finalist met
its frozen automated acceptance gate. Step 4B therefore performs a blinded
**diagnostic** review and writes a policy-enforced decision record.

The human review cannot override a failed automated gate. The permitted outcome
for the current frozen evidence is:

- no finalist selected;
- the existing production baseline retained unchanged;
- retention is a no-change safety decision, not a claim that the baseline passed.

## Files

```text
README_PHASE_6_STEP_4B.md
evaluation/llm_finalist_human_review.py
scripts/review_llm_finalists.py
tests/unit/test_llm_finalist_human_review.py
```

## Quality gates

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit/test_llm_finalist_human_review.py -v
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

## Prepare the offline review

```bash
uv run python -m scripts.review_llm_finalists --prepare
```

Reviewer-facing files are written under:

```text
artifacts/llm_evaluation/v1/gpt-5-mini/finalist_confirmation/human_review/
```

Open only:

- `review_instructions.md`
- `blinded_responses.csv`
- `scores.csv`

Do not open `blinding_key.json` until finalization succeeds.

## Finalize

```bash
uv run python -m scripts.review_llm_finalists \
  --finalize \
  --reviewer-id "Dums"
```

Finalization validates the frozen raw-output SHA, context SHA, review-set
fingerprint, row identities, locked failure rows, and score completeness before
unblinding. It writes:

- `summary.json` and `summary.md` — diagnostic human results;
- `decision_record.json` and `decision_record.md` — policy outcome.

This workflow makes zero external calls and does not edit production prompt
instructions.
