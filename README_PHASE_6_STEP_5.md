# Phase 6 Step 5 — Reproducible Evaluation Evidence

Step 5 creates one deliberate, self-contained evidence directory from the frozen
Phase 6 contracts, tracked evaluation workflows, and all 25 generated evidence
files. The rest of `artifacts/llm_evaluation/` remains ignored.

The package validates the source record before copying anything:

- 12 frozen contexts;
- 36 primary attempts and six first-run contract failures;
- 36 primary automated-score rows and 36 human-score rows;
- 24 finalist attempts and three first-run contract failures;
- 24 finalist automated-score rows and 24 human-score rows;
- 55 total generation calls;
- estimated total evaluation cost of USD 0.17483089;
- final decision `no_finalist_selected`;
- retained prompt `production_baseline_v1`;
- no production prompt change;
- human review cannot override a failed automated gate.

## Files

```text
README_PHASE_6_STEP_5.md
evaluation/llm_evidence_package.py
scripts/package_llm_evidence.py
tests/unit/test_llm_evidence_package.py
```

## Quality gates

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit/test_llm_evidence_package.py -v
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

## Commit the packaging workflow first

```bash
git add \
  README_PHASE_6_STEP_5.md \
  evaluation/llm_evidence_package.py \
  scripts/package_llm_evidence.py \
  tests/unit/test_llm_evidence_package.py

git commit -m "feat: add Phase 6 evidence packaging (refs #9)"
git push
```

The evidence builder requires a clean working tree so that its manifest records a
stable source commit.

## Create the evidence set

```bash
uv run python -m scripts.package_llm_evidence --prepare
```

This writes the ignored directory:

```text
artifacts/llm_evaluation/v1/gpt-5-mini/phase6_evidence/
```

The directory contains copied contracts, copied reproducibility code, copied
first-run evidence, documented commands, verification metadata, a manifest, and
SHA-256 checksums.

## Verify

```bash
uv run python -m scripts.package_llm_evidence --verify
```

## Final Phase 6 commit

Only after verification succeeds, force-add the deliberate evidence directory:

```bash
git add -f \
  artifacts/llm_evaluation/v1/gpt-5-mini/phase6_evidence

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "docs: preserve Phase 6 LLM evaluation evidence (Closes #9)"
git push
```

Do not force-add any other path under `artifacts/llm_evaluation/`.
