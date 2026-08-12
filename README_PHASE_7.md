# Phase 7 - Dual Interface and Operational Monitoring

Phase 7 turns Pliris from a backend RAG service into a usable product with
two deliberately different interfaces. Public reviewers receive a simple,
anonymous chatbot. Developers receive a protected operational workspace for
sources, feedback, monitoring, and health diagnostics. Both experiences run
from the same Streamlit and FastAPI codebase and keep provider credentials
on the server.

## What Phase 7 delivers

1. A public chat-only interface with anonymous session isolation, bounded
   usage, grounded answers, citations, clear error states, and conversation
   clearing.
2. A protected developer interface with source inspection and controlled PDF
   staging and lifecycle actions.
3. Response-level helpful/not-helpful feedback and a protected feedback
   inspection workspace.
4. Privacy-safe operational event storage that rejects prompts, responses,
   secrets, identities, and session or message identifiers.
5. Aggregate dashboards for usage, scope decisions, latency, token volume,
   feedback, failures, and prompt-injection blocks.
6. Public-safe liveness and readiness plus protected dependency and
   non-secret configuration diagnostics.

## Architecture

The public and developer Streamlit services call the same FastAPI process.
Public requests use a shared server-to-server UI secret plus a signed guest
conversation token. Developer requests also require the developer access key.
The browser never receives OpenAI, Supabase, PostgreSQL, or internal API
credentials.

The health surface follows the same separation:

- GET /health/live returns only process liveness.
- GET /health/ready returns only ready or not_ready and uses HTTP 503 when a
  required dependency is unavailable.
- GET /health/config requires the developer key and returns a bounded,
  non-secret configuration projection.
- GET /health/diagnostics requires the developer key and returns API,
  Supabase Data API, and PostgreSQL status with probe latency.

Exception text, connection strings, credentials, prompts, responses, user
identities, and conversation, session, or message identifiers are excluded
from every health response and from the developer Health page.

## Step 6 code map

| Area | Files |
| --- | --- |
| Health routes and probes | api/routes/health.py |
| Protected client validation | app/services/health_client.py |
| Display helpers | app/health_view.py |
| Developer page | app/developer_pages/5_Health.py |
| Navigation and console | app/navigation.py, app/developer_pages/0_Developer.py |
| Automated coverage | Three health test modules under tests/unit/ |

## Important design decisions

Readiness performs real dependency probes, while liveness only proves that
the API process can answer. This distinction prevents a temporary database
outage from causing an orchestrator to treat the process as dead.

Public readiness is intentionally terse. Dependency names and failure
details are operational information, so they are available only through the
protected diagnostics route and developer interface. Even there, failures
are represented as unavailable rather than returning raw exception text.

The developer client validates the complete diagnostics structure, rejects
unknown or duplicate checks, verifies that HTTP status agrees with the
readiness status, and blocks known private-field names recursively. A
malformed backend response therefore becomes a safe UI error instead of
being rendered directly.

## Configuration

Local developer mode requires the normal application variables plus:

    GUEST_UI_SHARED_SECRET=replace_with_a_long_random_secret
    DEVELOPER_UI_ACCESS_KEY=replace_with_a_long_developer_access_code

Start the local stack:

    docker compose --profile developer up --build -d

Open:

- public chat: http://localhost:8501
- protected developer UI: http://localhost:8502
- FastAPI docs: http://localhost:8000/docs

## Verification

The pre-Step-6 baseline was 456 passing tests with five known dependency
deprecation warnings. This batch adds fourteen tests, so the expected full
regression result is 470 passed with the same five non-blocking warnings.

Run:

    uv run ruff format api/routes/health.py app/health_view.py           app/services/health_client.py app/developer_pages/5_Health.py           tests/unit/test_health_route.py tests/unit/test_health_client.py           tests/unit/test_health_view.py app/navigation.py           app/developer_pages/0_Developer.py tests/unit/test_api_main.py           tests/unit/test_ui_navigation.py
    uv run ruff check .
    uv run pytest -q
    git diff --check
    git status --short

Live acceptance must confirm:

- /health/live returns HTTP 200 and only status ok.
- /health/ready returns HTTP 200 when dependencies are available.
- /health/diagnostics rejects a missing developer key and returns a
  structured response with the correct key.
- Health & Readiness appears only in the authenticated developer navigation.
- Refresh works and the three service cards plus non-secret configuration
  render without raw errors or private values.
- The public UI remains chat-only.

## Problems caught during Phase 7

Phase 7 verification found and corrected several integration issues:

- configuration names differed between Docker and validated settings;
- the developer access key was initially absent from the API container;
- hard-coded localhost calls prevented container-to-container routing;
- placeholder developer pages exposed unsafe raw errors and cross-user data;
- a dark-theme style made copy controls difficult to see;
- multiline terminal patches could be corrupted during paste.

The final implementation uses centralized configuration, explicit protected
routes, safe client error translation, privacy allowlists and denylists,
offline unit tests, Docker acceptance, and guarded installer preflight.

## Phase boundary

Phase 7 is complete when the automated and live gates above pass, the branch
is synchronized, and issue #10 records the sanitized evidence. Phase 8 can
then begin as a consolidated batch without reopening Phase 7 scope.
