# Phase 4 Step 4 - Grounded Chat API Route

This increment replaces the legacy chat-route orchestration path with the
production grounded pipeline from Phase 4 Steps 1 through 3.

It preserves prompt-injection detection, scope classification, the exact
out-of-scope response, and the existing `/stream` not-implemented response.

It does not implement database persistence or change the Streamlit UI.

## Files

```text
api/routes/chat.py
api/schemas/chat.py
tests/unit/test_chat_route.py
README_PHASE_4_STEP_4.md
```

## Behaviour

The revised chat route:

- avoids constructing the old legacy orchestrator at import time;
- injects and caches `GroundedResponseOrchestrator`,
  `ScopeClassifier`, and `PromptInjectionDetector`;
- blocks prompt injection before scope classification;
- preserves the exact approved out-of-scope response;
- invokes the production hosted retrieval and grounded generation pipeline for
  in-scope questions;
- optionally reads `document_id` from `request.context`;
- returns validated citations and grounded-pipeline metadata;
- exposes `insufficient_evidence`, model, response ID, token usage, retrieval
  details, context details, and latency metrics under response metadata;
- converts unexpected failures to the existing generic HTTP 500 response;
- keeps `/stream` at HTTP 501.

The existing legacy `pliris/agents/orchestrator.py` remains in the repository
for now, but the chat route no longer imports or uses it.

## Schema compatibility

`Citation` retains its original required fields:

```text
source
title
text
page
score
metadata
```

It adds optional grounded fields:

```text
citation_id
chunk_id
page_start
page_end
rank
document_id
```

`ChatResponse` retains its original fields and replaces mutable list/dict
defaults with Pydantic `default_factory` values.

## Pre-extraction verification

Confirm Phase 4 Step 3 is committed and the branch is clean:

```bash
git status --short
git --no-pager log -3 --oneline
```

Expected recent commit:

```text
9cd95c2 feat: add grounded pipeline orchestrator
```

Extract this package into the repository root while remaining on:

```text
feature-grounded-response-pipeline
```

The package replaces:

```text
api/routes/chat.py
api/schemas/chat.py
```

and adds:

```text
tests/unit/test_chat_route.py
README_PHASE_4_STEP_4.md
```

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_chat_route.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
9 passed
```

The non-integration total should increase from 81 to approximately 90. The
integration count should remain 12.

## What the route tests verify

The focused suite verifies:

- in-scope requests reach the grounded pipeline;
- citation metadata serializes through `ChatResponse`;
- `document_id` is normalized and forwarded;
- the exact out-of-scope response is preserved;
- prompt injection is blocked before scope classification;
- insufficient evidence returns no citations and zero confidence;
- unexpected pipeline errors become HTTP 500;
- `/stream` remains HTTP 501;
- FastAPI dependency overrides work through a real `TestClient` request.

## Live production-route smoke test

This creates a temporary FastAPI application around the production router and
performs scope classification, hosted retrieval, and grounded generation. It
uses paid OpenAI calls.

```bash
uv run python - <<'PY'
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.chat import router


app = FastAPI()
app.include_router(router, prefix="/chat")
client = TestClient(app)

response = client.post(
    "/chat/",
    json={
        "message": "What is requirements traceability?",
        "conversation_id": "route-smoke-test",
        "context": {"document_id": "babok-v3"},
    },
)

print("status:", response.status_code)
print(response.json())
response.raise_for_status()
PY
```

Expected characteristics:

- HTTP status `200`;
- `scope` is an in-scope category;
- `response` contains inline `[S#]` citations;
- `citations` contains only cited source metadata;
- `confidence` is `1.0` under the validated citation contract;
- `conversation_id` is passed through;
- `metadata.model`, `metadata.response_id`, and token usage are present;
- retrieval and generation latency values are present.

## Exact out-of-scope smoke test

This may call the scope classifier but does not run retrieval or generation:

```bash
uv run python - <<'PY'
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.chat import OUT_OF_SCOPE_RESPONSE, router


app = FastAPI()
app.include_router(router, prefix="/chat")
client = TestClient(app)

response = client.post(
    "/chat/",
    json={"message": "What is the score of today's hockey game?"},
)

payload = response.json()
print("status:", response.status_code)
print(payload)
assert response.status_code == 200
assert payload["response"] == OUT_OF_SCOPE_RESPONSE
assert payload["citations"] == []
assert payload["confidence"] == 0.0
PY
```

## Review checkpoints

Before committing, confirm:

- `api/routes/chat.py` imports `GroundedResponseOrchestrator`;
- it does not import `AgentOrchestrator`;
- the out-of-scope text is unchanged character-for-character;
- prompt injection is evaluated before scope classification;
- in-scope responses include grounded metadata;
- no repository, persistence, or Streamlit file changed;
- the full test suite remains green.

## Commit

```bash
git status --short

git add \
  README_PHASE_4_STEP_4.md \
  api/routes/chat.py \
  api/schemas/chat.py \
  tests/unit/test_chat_route.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: connect grounded pipeline to chat API"
git push
```

## Next increment

Phase 4 Step 5 will implement real Supabase persistence for:

- conversations;
- user and assistant messages;
- retrieval queries and results;
- monitoring events.

Persistence will be dependency-injected and fail without replacing a valid
grounded answer unless the selected event is explicitly required.
