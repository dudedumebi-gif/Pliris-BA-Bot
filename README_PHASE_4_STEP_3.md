# Phase 4 Step 3 - Grounded Pipeline Orchestrator

This increment connects the hosted hybrid retriever, deterministic context
assembler, and validated Responses API generator through one production
pipeline contract.

It does not modify the existing FastAPI route, legacy orchestrator, Streamlit
UI, or database repositories.

## Files

```text
pliris/agents/grounded_orchestrator.py
tests/unit/test_grounded_orchestrator.py
README_PHASE_4_STEP_3.md
```

## Behaviour

`GroundedResponseOrchestrator`:

- accepts injected retrieval, assembly, and generation dependencies;
- uses hosted hybrid retrieval with five results by default;
- does not invoke query rewriting or the rejected local reranker;
- builds deterministic `[S1]` through `[S5]` context;
- invokes the validated grounded generator;
- joins cited source IDs back to original retrieved chunks;
- exposes API-ready citation text, source, page, score, rank, chunk, document,
  and metadata fields;
- returns zero confidence for insufficient-evidence results;
- labels successful confidence as a validated-citation-contract signal rather
  than a probabilistic truth score;
- captures retrieval, assembly, generation, and total elapsed time;
- does not write conversations, messages, retrieval records, or monitoring
  events yet.

## Pre-extraction verification

Phase 4 Step 2 should now include the successful commit:

```text
975e805 feat: add grounded response generation
```

Confirm the branch is clean before extraction:

```bash
git status --short
git --no-pager log -3 --oneline
```

When `git status --short` is empty, extract this package into the repository
root while remaining on:

```text
feature-grounded-response-pipeline
```

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_grounded_orchestrator.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
5 passed
```

The non-integration total should increase from 76 to approximately 81. The
integration count should remain 12.

## Live end-to-end pipeline test

This performs hosted retrieval and one paid OpenAI Responses API call:

```bash
uv run python - <<'PY'
import asyncio
import json

from pliris.agents.grounded_orchestrator import (
    GroundedResponseOrchestrator,
)


async def main() -> None:
    result = await GroundedResponseOrchestrator().process_query(
        message="What is requirements traceability?",
        conversation_id="manual-smoke-test",
        user_id="system",
        document_id="babok-v3",
    )
    print(json.dumps(result.to_dict(), indent=2))


asyncio.run(main())
PY
```

Expected characteristics:

- `response` contains inline source identifiers;
- `citations` contains only identifiers used by the answer;
- citation excerpts and pages map back to the retrieved chunks;
- `confidence` is `1.0` only because the citation contract validated;
- `metadata.confidence_basis` is
  `validated_citation_contract`;
- retrieval, assembly, generation, and total timing values are present;
- `conversation_id` is passed through but not persisted.

## No-evidence test

This test uses injected fakes and makes no paid call:

```bash
uv run pytest \
  tests/unit/test_grounded_orchestrator.py::test_pipeline_returns_zero_confidence_when_insufficient \
  -v
```

## Review checkpoints

Before committing, confirm:

- the pipeline uses `HostedHybridRetriever`;
- the pipeline does not import the legacy `HybridSearch`, `QueryRewriter`, or
  `Reranker`;
- cited excerpts correspond to cited chunk IDs;
- insufficient evidence returns no citations and zero confidence;
- no route, UI, or repository files changed;
- the complete test suite remains green.

## Commit

```bash
git status --short

git add \
  README_PHASE_4_STEP_3.md \
  pliris/agents/grounded_orchestrator.py \
  tests/unit/test_grounded_orchestrator.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: add grounded pipeline orchestrator"
git push
```

## Next increment

Phase 4 Step 4 will replace the legacy chat-route orchestration path with this
grounded pipeline while preserving:

- prompt-injection detection;
- the exact out-of-scope response;
- the existing request and response schema;
- dependency-injected route tests;
- no persistence writes until the repository layer is implemented.
