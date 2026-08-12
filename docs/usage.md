# Usage

## Public review session

Open <http://localhost:8501>. The public surface contains chat only. Ask about requirements
elicitation, stakeholder analysis, traceability, process modelling, acceptance criteria, delivery
planning, or project risk. Responses are scope-checked, injection-checked, grounded in retrieved
evidence, and accompanied by citations when sufficient evidence exists.

The UI creates an opaque guest session and the API enforces both rolling-window and per-session
limits. Clearing the conversation does not reset those limits.

## Developer workspace

Open <http://localhost:8502> and unlock with `DEVELOPER_UI_ACCESS_KEY`. The workspace provides:

- chat for authenticated testing;
- source inventory, protected PDF staging, lifecycle controls, and chunks;
- structured response feedback;
- privacy-bounded monitoring events and aggregate metrics;
- API liveness, dependency readiness, and a non-secret configuration view.

Developer endpoints require `X-Pliris-Developer-Key`. A missing or wrong key receives `401` and
diagnostics never expose credentials, connection strings, exception text, prompts, responses, user
identities, or conversation/message identifiers.

## Health checks

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl -H "X-Pliris-Developer-Key: $DEVELOPER_UI_ACCESS_KEY" \
  http://localhost:8000/health/diagnostics
```

Liveness answers whether the process can receive requests. Readiness checks Supabase Data API and
Postgres. Protected diagnostics add dependency names, bounded latency, and non-secret settings.

## Source staging and ingestion

Register a PDF in `data/corpus_manifest.yaml`, unlock the developer Sources page, upload the exact
PDF, and note the staged document UUID. Then run:

```bash
uv run python -m scripts.ingest_document \
  --document-id MANIFEST_ID \
  --staged-document-id DATABASE_DOCUMENT_UUID
```

Use `--dry-run` first to inspect extraction and chunking without database writes or embeddings. A
successful run changes the document from `pending` to `ready`; failed runs preserve an auditable
error state. The public sample manifest ID is `pliris-public-ba-primer`.

## Evaluation

Run the locked retrieval and generation evaluation tooling described in [evaluation](evaluation.md).
Generated evidence belongs under `artifacts/` and private source content must never be committed.
