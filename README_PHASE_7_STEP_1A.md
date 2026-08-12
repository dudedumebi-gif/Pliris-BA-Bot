# Phase 7 Step 1A — Public Chat Backend Contract

This increment prepares the existing FastAPI backend for a guest-safe public
chat interface. It does not deploy the Streamlit UI or expose developer
analytics.

## Changes

- Registers the existing guarded chat router under `/api/chat`.
- Replaces the shared system identity with a validated anonymous session
  identity.
- Supports a server-to-server shared secret between Streamlit and FastAPI.
- Adds conservative rolling-window and per-session request limits.
- Keeps rate-limit state process-local for the public-review phase.
- Aligns Docker environment names with the validated application settings.
- Removes stale dependency references to undefined authentication settings.
- Preserves the exact out-of-scope response and all existing grounded-pipeline
  contracts.
- Adds offline tests for route registration, access validation, session
  isolation, and request limiting.

## Security boundary

The shared secret is never sent to browser JavaScript. Streamlit sends it from
its server process to FastAPI. In production, `APP_ENV=production` requires
`GUEST_UI_SHARED_SECRET`.

The in-memory limiter is appropriate for a conservative single-instance review
deployment. Phase 7 monitoring storage can replace it with a shared persistent
limiter before multi-instance scaling.

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest tests/unit/test_chat_route.py tests/unit/test_guest_access.py tests/unit/test_api_main.py -q
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```
