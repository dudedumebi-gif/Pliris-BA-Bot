# Phase 3 Step 1 - BABOK Layout Audit

This increment is diagnostic only. It does not alter chunks, call OpenAI,
write to Supabase, or reingest BABOK.

## Rename the branch before pushing

The remote already has a branch named `feat`, so the current slash-based branch
will fail on push:

```bash
git branch -m feature-pdf-extraction-quality
```

## Merge the package

Copy these files into the repository root:

```text
ingestion/layout_audit.py
scripts/audit_babok_layout.py
tests/unit/test_layout_audit.py
README_PHASE_3_STEP_1.md
```

## Run checks

```bash
uv run ruff format .
uv run ruff check .
uv run pytest tests/unit/test_layout_audit.py -v
```

## Run the complete BABOK audit

```bash
uv run python -m scripts.audit_babok_layout \
  --document-id babok-v3
```

Outputs:

```text
artifacts/layout_audit/babok-v3_layout_audit.json
artifacts/layout_audit/babok-v3_layout_audit.txt
```

## Keep generated audit output out of Git

Add this rule when it is not already present:

```gitignore
artifacts/layout_audit/*
!artifacts/layout_audit/.gitkeep
```

Do not run BABOK ingestion with `--force` during this diagnostic step.
