# Phase 3 Step 4 - Local Cross-Encoder Reranker

The hardened BABOK benchmark shows that hosted hybrid retrieval is the best
current baseline, but direct-answer ranking still needs improvement:

- hybrid MRR: 0.833;
- hybrid Hit@1: 0.700;
- hybrid Precision@3: 0.567;
- hybrid evidence Recall@5: 0.920.

This increment evaluates a local open-source cross-encoder against that frozen
baseline. It does not change production chat retrieval yet.

## Design

The new `hybrid_reranked` method:

1. retrieves 20 candidates from the existing hosted hybrid RPC;
2. scores each query-passage pair locally;
3. sorts by cross-encoder score;
4. returns the requested top five results.

Default model:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

The model is loaded lazily and cached in memory for the process. The existing
benchmark warm-up run loads the model before measured requests.

## Files

```text
evaluation/local_reranker.py
evaluation/reranked_retriever.py
evaluation/retrieval_runner.py
tests/unit/test_local_reranker.py
README_PHASE_3_STEP_4.md
```

`evaluation/retrieval_runner.py` replaces the Step 3B version and adds
`hybrid_reranked` to the supported benchmark methods.

## Install the pinned dependency

The package deliberately does not overwrite `pyproject.toml`.

From the repository root, add the dependency through uv:

```bash
uv add "sentence-transformers==5.6.0"
uv lock
uv sync --all-extras
```

The first model load downloads the model into the normal Hugging Face cache,
not into the Git repository.

## Extract

Extract the package into the repository root while remaining on:

```text
feature-retrieval-quality
```

Allow this file to be replaced:

```text
evaluation/retrieval_runner.py
```

Do not modify the existing production file:

```text
pliris/retrieval/reranker.py
```

This increment is evaluation-only until the benchmark proves an improvement.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_retrieval_benchmark.py \
  tests/unit/test_hosted_retriever.py \
  tests/unit/test_local_reranker.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
26 passed
```

Expected non-integration count:

```text
approximately 49 passed, 12 deselected
```

## Optional model warm-up

This confirms the dependency and downloads the model before the benchmark:

```bash
uv run python - <<'PY'
from sentence_transformers import CrossEncoder

model = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L6-v2",
    max_length=512,
    device="cpu",
)
print(type(model).__name__)
PY
```

## Run the reranker comparison

Run hosted hybrid and reranked hybrid in the same process:

```bash
uv run python -m scripts.evaluate_retrieval \
  --methods hybrid hybrid_reranked \
  --top-k 5 \
  --document-id babok-v3 \
  --repetitions 3 \
  --warmup-count 1 \
  --output-directory artifacts/retrieval_evaluation/reranker
```

Review:

```bash
cat artifacts/retrieval_evaluation/reranker/retrieval_baseline.md
```

The reranked method's measured latency includes:

- hosted hybrid retrieval of 20 candidates;
- local cross-encoder inference;
- final sorting.

The model-download and model-load cold start should occur during warm-up and
therefore remain outside the measured samples.

## Inspect rank movement

```bash
uv run python - <<'PY'
import json
from pathlib import Path

path = Path(
    "artifacts/retrieval_evaluation/reranker/"
    "retrieval_baseline.json"
)
report = json.loads(path.read_text(encoding="utf-8"))

for method in ("hybrid", "hybrid_reranked"):
    print(f"\n=== {method.upper()} ===")
    for case in report["methods"][method]:
        print(
            case["case_id"],
            "first=",
            case["first_relevant_rank"],
            "p@3=",
            case["precision_at_3"],
            "recall@5=",
            case["evidence_recall_at_5"],
            "median_ms=",
            case["median_latency_ms"],
        )
        for result in case["results"][:3]:
            metadata = result.get("metadata") or {}
            print(
                result["rank"],
                f"{result['page_start']}-{result['page_end']}",
                "relevant=",
                result["relevant"],
                "original_rank=",
                metadata.get("original_rank"),
                "rerank_score=",
                metadata.get("rerank_score"),
                result["snippet"][:180],
            )
PY
```

## Decision rule

The reranker should not be promoted to production merely because one query
improves.

A strong result should:

- improve MRR and Hit@1 over the hardened hybrid baseline;
- improve or preserve Precision@3;
- preserve evidence Recall@5 at or above the hybrid baseline;
- keep ranking stable across repeated runs;
- provide a latency trade-off acceptable for an interactive assistant.

If the reranker improves definitions but harms task-oriented questions, inspect
the moved candidates before changing the model, candidate pool, or score
blending.


# Sentence Transformers evalution-only
The rereranker was rejected for production, so sentence-transformers should not remain in the 
main runtime dependencies.
Run:
```bash
uv add --group evaluation "sentence-transformers==5.6.0"
uv sync --group evaluation
```

The final reranker command begins with:
```bash
uv run --group evaluation python -m scripts.evaluate_retrieval \
  --methods hybrid hybrid_reranked \
  --top-k 5 \
  --document-id babok-v3 \
  --repetitions 3 \
  --warmup-count 1 \
  --output-directory artifacts/retrieval_evaluation/reranker
```