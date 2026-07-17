# Phase 3 Step 3A - Hosted Retrieval Baseline Adapter

The first baseline run did not measure retrieval quality. It exercised legacy
retrieval classes that are not wired to the hosted BABOK index:

- `LexicalSearch` requires an in-memory BM25 index to be built first;
- `SemanticSearch` calls an unexecuted Supabase RPC builder;
- `HybridSearch` combines those two incomplete paths.

The working production smoke test already uses the hosted `hybrid_search` RPC.
This patch makes the evaluation harness use that same authoritative path.

## Files

```text
evaluation/hosted_retriever.py
evaluation/retrieval_runner.py
tests/unit/test_hosted_retriever.py
README_PHASE_3_STEP_3A.md
```

`evaluation/retrieval_runner.py` replaces the Step 3 version. It retains the
empty-result failure guard.

## Comparison method

All three retrieval modes call the same hosted SQL function and indexed corpus:

```text
lexical:  full_text_weight=1.0, semantic_weight=0.0
semantic: full_text_weight=0.0, semantic_weight=1.0
hybrid:   configured project weights
```

This avoids comparing the production hybrid RPC against unrelated legacy
Python scaffolding.

The RPC still receives a query embedding in lexical mode because the current
SQL function contract requires `query_embedding`. Ranking is lexical because
the semantic arm is assigned zero weight. Latency therefore includes query
embedding time for all three methods.

## Merge

Extract the package into the repository root on:

```text
feature-retrieval-quality
```

Allow this file to be replaced:

```text
evaluation/retrieval_runner.py
```

Do not modify these production files yet:

```text
pliris/retrieval/lexical_search.py
pliris/retrieval/semantic_search.py
pliris/retrieval/hybrid_search.py
```

They can be refactored after the benchmark establishes the preferred hosted
retrieval design.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .

uv run pytest \
  tests/unit/test_retrieval_benchmark.py \
  tests/unit/test_hosted_retriever.py \
  -v

uv run pytest -m "not integration" -q
```

Expected focused count:

```text
15 passed
```

The current benchmark suite has nine tests and the hosted adapter adds six
test instances, including the three parameterized retrieval modes.

## Remove the invalid report

The zero-result report is not a baseline:

```bash
rm -f artifacts/retrieval_evaluation/retrieval_baseline.json
rm -f artifacts/retrieval_evaluation/retrieval_baseline.csv
rm -f artifacts/retrieval_evaluation/retrieval_baseline.md
```

The directory is ignored, so this does not affect Git history.

## Run the real baseline

```bash
uv run python -m scripts.evaluate_retrieval \
  --methods lexical semantic hybrid \
  --top-k 5 \
  --document-id babok-v3
```

A valid run should have:

- no `Lexical index not built` messages;
- no `SyncRPCFilterRequestBuilder` errors;
- non-empty results for every method and case;
- `error_count: 0`;
- non-zero relevance metrics for at least the page-verified cases.

Review:

```bash
cat artifacts/retrieval_evaluation/retrieval_baseline.md
```

Do not tune weights until the JSON and Markdown results have been reviewed.
