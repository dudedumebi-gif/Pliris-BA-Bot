# Pliris BA Bot — Phase 2: One-Document Ingestion

This increment adds the first complete ingestion path:

```text
Private PDF
→ manifest validation
→ page-aware extraction
→ text cleaning
→ token-aware chunking
→ OpenAI embeddings
→ private Supabase Storage
→ documents/document_chunks
→ hybrid-search validation
```

## 1. Create the branch

```bash
git checkout -b feat/document-ingestion
```

## 2. Merge this package

Copy the package contents into the existing repository root.

The package uses new Phase 2 module names so it does not overwrite the earlier
course-derived placeholder modules.

## 3. Confirm the BABOK filename

The manifest expects:

```text
data/private/BABOK_Guide_v3.pdf
```

If the actual filename differs, update only `source_filename` in:

```text
data/corpus_manifest.yaml
```

The PDF must remain private and ignored by Git.

## 4. Apply the migration

Run this file in the hosted Supabase SQL Editor:

```text
supabase/migrations/202607150002_add_document_manifest_id.sql
```

It adds a stable `manifest_id` to `documents` and a unique partial index for
idempotent upserts.

Verify:

```sql
select column_name
from information_schema.columns
where table_schema = 'public'
  and table_name = 'documents'
  and column_name = 'manifest_id';
```

## 5. Confirm dependencies

The ingestion dependency group needs:

```text
pymupdf
pyyaml
tiktoken
```

Run:

```bash
uv sync --all-extras
```

## 6. Run a low-cost dry run

This performs no upload, database write, embedding call, or API charge:

```bash
uv run python -m scripts.ingest_document \
  --document-id babok-v3 \
  --dry-run \
  --max-pages 20
```

Review:

- pages inspected
- chunks produced
- estimated embedding tokens
- extraction warnings

Then inspect the complete document locally:

```bash
uv run python -m scripts.ingest_document \
  --document-id babok-v3 \
  --dry-run
```

## 7. Run unit tests

```bash
uv run pytest -m "not integration" -v
```

## 8. Ingest BABOK into hosted Supabase

This performs real OpenAI embedding calls:

```bash
uv run python -m scripts.ingest_document \
  --document-id babok-v3
```

A successful result has nonzero page and chunk counts and:

```json
{
  "document_id": "babok-v3",
  "status": "completed",
  "storage_path": "babok-v3/BABOK_Guide_v3.pdf"
}
```

Running the same command again should return:

```json
{
  "status": "skipped"
}
```

Use `--force` only when intentionally replacing all embeddings and chunks:

```bash
uv run python -m scripts.ingest_document \
  --document-id babok-v3 \
  --force
```

## 9. Verify in Supabase

```sql
select
  manifest_id,
  title,
  status,
  page_count,
  storage_path,
  last_ingested_at
from public.documents
where manifest_id = 'babok-v3';
```

```sql
select
  count(*) as chunk_count,
  min(page_start) as first_page,
  max(page_end) as last_page,
  min(embedding_dimensions) as min_dimensions,
  max(embedding_dimensions) as max_dimensions
from public.document_chunks dc
join public.documents d on d.id = dc.document_id
where d.manifest_id = 'babok-v3';
```

Expected embedding dimensions:

```text
1536
```

## 10. Run a retrieval smoke test

```bash
uv run python -m scripts.search_knowledge_base \
  "What is business analysis?" \
  --document-id babok-v3
```

The results should include:

- BABOK title
- page range
- hybrid score
- text snippet

## 11. Run the isolated hosted integration test

This test creates its own tiny PDF, embeds it, retrieves it, verifies
idempotency, and deletes its database and Storage records:

```bash
uv run pytest tests/integration/test_phase2_document_ingestion.py -v
```

## 12. Quality and regression checks

```bash
uv run ruff format .
uv run ruff check .
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

## Phase 2 acceptance criteria

- BABOK appears in the private `knowledge-base` bucket.
- Its document row has `status = 'ready'`.
- Its chunks include page ranges and deterministic hashes.
- Every chunk has a 1536-dimensional embedding.
- Full-text vectors are populated by the database trigger.
- Hybrid search returns BABOK passages with page metadata.
- A second identical ingestion is skipped.
- All unit and integration tests pass.
- `data/private/BABOK_Guide_v3.pdf` remains ignored by Git.
