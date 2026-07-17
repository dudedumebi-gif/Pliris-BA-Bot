# Phase 3 Step 3B - Retrieval Benchmark Hardening

The first hosted benchmark established that the production Supabase RPC works,
but its relevance and latency measurements were too generous for retrieval
tuning.

This increment freezes a stricter baseline before reranking.

## Why the benchmark changes

The earlier relevance rule accepted a result when either:

- its page range overlapped an expected range; or
- it matched the expected concepts.

That classified introductory, diagram-heavy, and adjacent passages as relevant
even when they could not directly answer the question.

Version 2 requires both:

```text
expected page overlap
AND
minimum expected concept coverage
```

All ten benchmark cases now have reviewed page ranges.

## Files

```text
data/evaluation/retrieval_benchmark.json
evaluation/retrieval_benchmark.py
evaluation/hosted_retriever.py
evaluation/retrieval_metrics.py
evaluation/retrieval_runner.py
scripts/evaluate_retrieval.py
tests/unit/test_retrieval_benchmark.py
README_PHASE_3_STEP_3B.md
```

The benchmark and hosted adapter files are included so the package is
self-contained. Their public interfaces remain compatible with Step 3A.

## Measurement changes

Each retrieval method now receives:

- one configurable warm-up search before measurement;
- three measured searches per question by default;
- median latency;
- p95 latency;
- ranking-stability verification across repetitions.

The report retains MRR, Hit@1, Hit@3, Precision@3, and evidence Recall@5.

## Extract

Extract the package into the repository root on:

```text
feature-retrieval-quality
```

Allow the listed files to be replaced.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_retrieval_benchmark.py \
  tests/unit/test_hosted_retriever.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
20 passed
```

The full non-integration count should increase from 38 to approximately 43
because the benchmark test module grows from 9 to 14 tests.

## Run the hardened baseline

Keep the provisional reports for comparison, but write the hardened run to a
new directory:

```bash
uv run python -m scripts.evaluate_retrieval \
  --methods lexical semantic hybrid \
  --top-k 5 \
  --document-id babok-v3 \
  --repetitions 3 \
  --warmup-count 1 \
  --output-directory artifacts/retrieval_evaluation/hardened
```

Review:

```bash
cat artifacts/retrieval_evaluation/hardened/retrieval_baseline.md
```

A valid run should show:

- `error_count: 0`;
- three latency samples for every method/query pair;
- `ranking_stable: True` for deterministic hosted ranking;
- lower or equal MRR and Precision@3 than the permissive baseline;
- no obvious definition or purpose passage marked relevant solely by page
  overlap.

## Inspect weak cases

```bash
uv run python - <<'PY'
import json
from pathlib import Path

path = Path(
    "artifacts/retrieval_evaluation/hardened/"
    "retrieval_baseline.json"
)
report = json.loads(path.read_text(encoding="utf-8"))

for method, cases in report["methods"].items():
    for case in cases:
        if (
            case["first_relevant_rank"] != 1
            or case["precision_at_3"] < 1.0
            or case["evidence_recall_at_5"] < 1.0
            or not case["ranking_stable"]
        ):
            print(f"\n{method.upper()} - {case['case_id']}")
            print(
                "first=",
                case["first_relevant_rank"],
                "p@3=",
                case["precision_at_3"],
                "recall@5=",
                case["evidence_recall_at_5"],
                "median_ms=",
                case["median_latency_ms"],
                "p95_ms=",
                case["p95_latency_ms"],
                "stable=",
                case["ranking_stable"],
            )
            for result in case["results"][:5]:
                print(
                    result["rank"],
                    f"{result['page_start']}-{result['page_end']}",
                    result["relevant"],
                    result["page_relevant"],
                    result["term_relevant"],
                    result["snippet"][:220],
                )
PY
```

## Decision after review

Do not tune fusion weights from the permissive benchmark.

Use the hardened report to identify:

- definition queries where hybrid fusion suppresses the best semantic result;
- task queries where lexical matching introduces adjacent sections;
- whether the same weak passages recur across methods;
- which cases need reranking rather than query rewriting.

The next increment is a local open-source reranker evaluated against this
frozen hardened baseline.
