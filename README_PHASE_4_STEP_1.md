# Phase 4 Step 1 - Hosted Hybrid Retrieval and Context Assembly

This increment introduces the first production components of the grounded
response pipeline without changing the API, Streamlit application, agent
orchestrator, generation client, or persistence layer.

## Audit conclusion

The current endpoint already applies prompt-injection and scope checks, but the
orchestrator still uses the legacy in-memory/placeholder retrieval and
reranking classes. Generation, evidence checking, response guardrails, and
conversation persistence also contain scaffold or placeholder behaviour.

This step replaces none of those modules yet. It establishes a tested
production retrieval contract first.

## Files

```text
pliris/retrieval/models.py
pliris/retrieval/hosted_hybrid.py
pliris/generation/context_assembler.py
scripts/inspect_grounded_context.py
tests/unit/test_hosted_hybrid.py
tests/unit/test_context_assembler.py
README_PHASE_4_STEP_1.md
```

## Production retrieval contract

`HostedHybridRetriever`:

- calls the hosted Supabase `hybrid_search` RPC;
- uses the configured full-text, semantic, and RRF weights;
- generates query embeddings using the existing ingestion embedding service;
- supports an optional manifest document filter;
- caches manifest-to-database-ID resolution;
- normalizes RPC rows into immutable `RetrievedChunk` objects;
- moves synchronous embedding and Supabase work off the async event loop;
- rejects blank queries and unreasonable result counts.

The selected retrieval strategy remains hosted Hybrid search. The rejected
cross-encoder remains in `evaluation/` only.

## Context assembly contract

`ContextAssembler`:

- accepts ranked `RetrievedChunk` objects;
- preserves retrieval rank;
- removes duplicate and empty chunks;
- includes at most five chunks by default;
- applies a deterministic character budget;
- assigns stable citation identifiers `[S1]` through `[S5]`;
- returns both prompt text and citation-ready source metadata;
- records omitted and truncated context.

No answer is generated in this step.

## Extract

Delete the diagnostic audit file:

```bash
rm -f phase4_pipeline_audit.txt
```

Extract this package into the repository root while on:

```text
feature-grounded-response-pipeline
```

The files are new and should not replace the existing legacy retrieval or
orchestrator modules.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_hosted_hybrid.py \
  tests/unit/test_context_assembler.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
14 passed
```

The project total should increase from 49 to approximately 63
non-integration tests. The integration count should remain 12.

## Live hosted smoke test

Run retrieval and context assembly against the BABOK corpus:

```bash
uv run python -m scripts.inspect_grounded_context \
  "What is requirements traceability?" \
  --document-id babok-v3 \
  --top-k 5
```

The JSON output should contain:

```text
retrieved_count: 5
chunks: five normalized hosted results
context.text: blocks labelled [S1] through [S5]
context.sources: citation-ready page and source metadata
context.omitted_count: 0
```

A result count below five is not automatically an error when the hosted corpus
has fewer matching chunks. An empty result returns exit code 2.

## Review checkpoints

Before the next increment, confirm:

- the hosted RPC parameters match the retrieval-quality benchmark;
- the direct BABOK definition or task evidence appears within the assembled
  context;
- citation labels and page ranges align with their source chunks;
- no API, UI, generation, or database repository files changed;
- all existing tests continue to pass.

## Next increment

Phase 4 Step 2 will build grounded OpenAI generation on top of
`AssembledContext`, including:

- the OpenAI Responses API;
- a strict context-only system contract;
- structured answer and citation output;
- insufficient-evidence handling;
- deterministic validation that cited source identifiers exist.

The orchestrator and API remain unchanged until the generation contract is
covered by tests.
