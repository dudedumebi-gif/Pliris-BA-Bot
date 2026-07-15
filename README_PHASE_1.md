# Pliris BA Bot — Phase 1 Foundation

This package is the first implementation increment after reviewing the five
course-code batches.

It does four things:

1. Consolidates the first production dependency set.
2. Validates the repository-root `.env`.
3. Tests the hosted Supabase project through both the Data API and PostgreSQL.
4. Starts a minimal FastAPI application with liveness and readiness endpoints.

## Why this differs from the course examples

The course examples provide valuable patterns for RAG, evaluation, monitoring,
and orchestration. Pliris keeps those patterns but replaces:

- DataTalks.Club FAQ ingestion with private BA and PM documents.
- MinSearch and local PostgreSQL with hosted Supabase and pgvector.
- Streamlit-to-database coupling with Streamlit → FastAPI → Supabase.
- Table-creation scripts that can drop data with version-controlled migrations.
- Hard-coded model prices with a later configurable model-cost registry.

## Files in this increment

```text
pyproject.toml
.env.example
Makefile
api/main.py
api/routes/health.py
pliris/config/settings.py
pliris/database/supabase_client.py
pliris/database/postgres.py
scripts/verify_environment.py
scripts/check_supabase.py
tests/unit/test_settings.py
tests/integration/test_supabase_connection.py
```

## Copy into the existing repository

Merge the package contents into the `pliris-ba-bot` repository root.

Do not replace the real `.env`. This package contains `.env.example` only.

## Install uv

Skip this step if `uv --version` already works.

### Linux/macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart the terminal after installation if `uv` is not immediately available.

## Install and lock dependencies

From the repository root:

```bash
uv sync --all-extras
uv lock
```

Commit both:

```text
pyproject.toml
uv.lock
```

The lock file supplies the exact resolved versions required by the
reproducibility rubric.

## Validate the `.env`

```bash
uv run python scripts/verify_environment.py
```

Expected final line:

```text
Environment validation passed.
```

The script masks all secrets and never prints full credentials.

## Run the hosted Supabase integration test

```bash
uv run python scripts/check_supabase.py
```

Expected checks:

```text
[PASS] Supabase Data API
[PASS] Private Storage bucket
[PASS] Database schema
[PASS] Public access restriction
[PASS] Write + hybrid retrieval
```

The final check creates one temporary document and chunk, calls the
`hybrid_search` RPC, and deletes the temporary record in a `finally` block.

## Run tests

```bash
uv run pytest -m "not integration"
uv run pytest -m integration
```

## Start the development API

```bash
uv run fastapi dev api/main.py
```

Then open:

```text
http://127.0.0.1:8000/docs
```

Useful endpoints:

```text
GET /health/live
GET /health/ready
GET /health/config
```

`/health/config` exposes only non-secret settings.

## Phase 1 acceptance criteria

Phase 1 is complete when:

- `uv sync --all-extras` succeeds.
- `uv.lock` exists.
- Environment validation passes.
- All five Supabase checks pass.
- Unit and integration tests pass.
- `GET /health/ready` returns HTTP 200.
- `.env` remains ignored by Git.
- No secret or copyrighted PDF is committed.

## Next development increment

After Phase 1 passes, build the ingestion vertical slice:

1. Corpus manifest loader.
2. PDF extraction with page preservation.
3. Cleaning and structure-aware chunking.
4. OpenAI embedding generation.
5. Private Storage upload.
6. Idempotent document and chunk upserts.
7. Ingestion-run audit records.
8. One-document end-to-end retrieval test.
