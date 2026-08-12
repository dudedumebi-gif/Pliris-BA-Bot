# Phase 7 Step 1B — Public Chat UI and Protected Developer Shell

## Deployment model

The same repository and Streamlit entrypoint support two deployments:

- `PLIRIS_UI_MODE=public`: a guest-safe, chat-only public interface.
- `PLIRIS_UI_MODE=developer`: a protected developer interface.

A public deployment receives a shareable URL. A second deployment of the same
codebase uses developer mode and requires `DEVELOPER_UI_ACCESS_KEY`.

## Public interface

- One anonymous UUID is generated per Streamlit browser session.
- The UUID and server-side UI shared secret are sent to FastAPI as headers.
- Chat history is visible only in the current Streamlit session.
- Clearing a conversation does not reset the guest identity or usage limits.
- API errors are translated into safe states for validation, guardrails, rate
  limits, timeouts, authorization failures, service outages, and server errors.
- Raw provider or backend exception details are never shown.
- Public navigation contains only Chat.

## Developer interface

- Developer mode requires an explicit access code before navigation is created.
- The protected shell currently contains Developer Console and Chat.
- Source inspection, feedback analytics, monitoring, dashboards, and health
  diagnostics will be added through Phase 7 Steps 2–6.
- Hiding a navigation link is not treated as access control.

## Local Docker use

Public UI:

```bash
docker compose up api streamlit
```

Protected developer UI:

```bash
docker compose --profile developer up api streamlit-developer
```

The public UI uses port 8501. The developer UI uses port 8502.

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest \
  tests/unit/test_ui_config.py \
  tests/unit/test_ui_auth.py \
  tests/unit/test_ui_navigation.py \
  tests/unit/test_chat_client.py \
  -q
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```
