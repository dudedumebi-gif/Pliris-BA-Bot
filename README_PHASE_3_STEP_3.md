# Phase 3 Step 3 - Retrieval Evaluation Harness

This increment creates a repeatable baseline before changing retrieval weights,
adding reranking, or enabling query rewriting.

It compares the existing Pliris retrieval implementations:

- lexical search;
- semantic/vector search;
- hybrid search.

## Files

```text
data/evaluation/retrieval_benchmark.json
evaluation/retrieval_benchmark.py
evaluation/retrieval_metrics.py
evaluation/retrieval_runner.py
scripts/evaluate_retrieval.py
tests/unit/test_retrieval_benchmark.py
artifacts/retrieval_evaluation/.gitkeep
README_PHASE_3_STEP_3.md
```

No database migration is included. The harness calls the existing
`LexicalSearch`, `SemanticSearch`, and `HybridSearch` classes.

## Benchmark design

Version 1 contains ten BABOK questions.

Page-verified cases include:

- business analysis definition;
- requirements traceability;
- stakeholder analysis;
- maintain requirements;
- requirements validation;
- requirements verification.

The remaining cases are keyword-seeded. They are useful for a baseline, but
their evidence annotations should be manually reviewed after the first run.

A result is considered relevant when either:

- its page range overlaps an expected page range; or
- it matches the minimum number of expected term groups.

This deterministic rule avoids using an LLM judge during the initial baseline.

## Metrics

The harness records:

- first relevant rank;
- reciprocal rank;
- Hit@1, Hit@3, and Hit@5;
- Precision@3;
- evidence Recall@5;
- retrieval latency;
- raw top-K result snippets.

Method-level summaries include mean reciprocal rank, hit rates, mean
Precision@3, mean evidence Recall@5, and mean latency.

## Merge the package

Extract the package into the repository root on
`feature-retrieval-quality`.

Add the following rules to `.gitignore`:

```gitignore
artifacts/retrieval_evaluation/*
!artifacts/retrieval_evaluation/.gitkeep
```

## Run checks

```bash
uv run ruff format .
uv run ruff check .
uv run pytest tests/unit/test_retrieval_benchmark.py -v
uv run pytest -m "not integration" -q
```

## Run the baseline

```bash
uv run python -m scripts.evaluate_retrieval \
  --methods lexical semantic hybrid \
  --top-k 5 \
  --document-id babok-v3
```

Generated reports:

```text
artifacts/retrieval_evaluation/retrieval_baseline.json
artifacts/retrieval_evaluation/retrieval_baseline.csv
artifacts/retrieval_evaluation/retrieval_baseline.md
```

The command exits with status 1 when any retrieval method fails to initialize
or search. The JSON and Markdown reports still record the errors so adapter or
interface mismatches can be corrected without losing successful method results.

## Review the baseline

Inspect the Markdown report:

```bash
cat artifacts/retrieval_evaluation/retrieval_baseline.md
```

Inspect the top results for the three existing smoke-test queries:

```bash
uv run python -c "
import json
from pathlib import Path

report = json.loads(
    Path(
        'artifacts/retrieval_evaluation/retrieval_baseline.json'
    ).read_text()
)
wanted = {
    'business_analysis_definition',
    'requirements_traceability_definition',
    'stakeholder_analysis',
}
for method, cases in report['methods'].items():
    print(f'\n=== {method.upper()} ===')
    for case in cases:
        if case['case_id'] not in wanted:
            continue
        print(
            case['case_id'],
            'first_relevant=',
            case['first_relevant_rank'],
            'p@3=',
            case['precision_at_3'],
        )
        for result in case['results'][:3]:
            print(
                result['rank'],
                result['page_start'],
                result['page_end'],
                result['relevant'],
                result['snippet'][:180],
            )
"
```

## Decision rule

Do not change hybrid weights yet.

The baseline should first establish:

- which method has the best MRR and Hit@1;
- where lexical search beats semantic search;
- where semantic search retrieves off-topic but related material;
- whether hybrid search consistently improves or merely averages the two;
- which keyword-seeded cases need corrected evidence annotations.

After reviewing the baseline, the next increment will add a local open-source
reranker and compare it against this unchanged baseline.
