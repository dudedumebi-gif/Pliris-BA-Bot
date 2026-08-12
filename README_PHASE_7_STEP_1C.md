# Phase 7 Step 1C — Streamlit Entrypoint and Page-Isolation Fix

## Defect

Launching `streamlit run app/Home.py` placed the `app` directory, rather than
the repository root, on the execution path. Absolute `app.*` imports failed
under Streamlit even though unit tests passed from the repository root.

When the entrypoint failed before `st.navigation()` completed, Streamlit fell
back to automatic multipage discovery and exposed every script under
`app/pages`, including developer-only scaffolding.

## Correction

- The canonical entrypoint is now repository-root `streamlit_app.py`.
- `app/Home.py` is removed.
- Public Chat remains under `app/pages`.
- Developer and future operational pages are stored under
  `app/developer_pages`, outside automatic page discovery.
- The active Developer Console also performs a page-level access check.
- Docker and local commands launch `streamlit_app.py`.
- Structural tests prevent the unsafe layout from returning.

## Local launch

Public:

```bash
export PLIRIS_UI_MODE=public
export API_URL=http://127.0.0.1:8000
uv run streamlit run streamlit_app.py --server.port 8501
```

Developer:

```bash
export PLIRIS_UI_MODE=developer
export API_URL=http://127.0.0.1:8000
uv run streamlit run streamlit_app.py --server.port 8502
```

Stop old Streamlit processes before switching modes. Environment changes do not
change an already-running process.

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest \
  tests/unit/test_ui_navigation.py \
  tests/unit/test_streamlit_layout.py \
  -q
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```
