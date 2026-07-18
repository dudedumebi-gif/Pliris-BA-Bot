# Phase 4 Step 5 - Transactional Grounded Persistence

This increment persists successful in-scope grounded interactions to the live
Supabase PostgreSQL schema.

It uses the schema that already exists in the hosted project. No database
migration is required.

## Audit findings applied

The live database already contains:

```text
conversations
messages
retrieval_queries
retrieval_results
monitoring_events
```

The implementation therefore uses the existing columns and constraints rather
than introducing guessed fields.

Important schema mappings:

- application `conversation_id` is stored as
  `conversations.client_session_id`;
- database conversation UUIDs remain internal;
- `user_id` is stored in monitoring-event properties because the
  `conversations` table has no `user_id` column;
- message citations use `messages.citations`;
- model and token usage use the dedicated message columns;
- component retrieval ranks use
  `retrieval_results.semantic_rank` and `keyword_rank`;
- no reranker score is stored because the rejected cross-encoder is not part
  of production;
- monitoring metadata uses `monitoring_events.properties`.

The existing scope classifier returns a validated category but does not return
a numeric probability. Until a calibrated classifier is introduced,
persistence stores `1.0` as discrete decision certainty and records:

```text
scope_confidence_basis = validated_discrete_scope_decision
```

This value must not be interpreted as a calibrated model probability.

## Files

```text
pliris/database/repositories/grounded_persistence.py
pliris/retrieval/hosted_hybrid.py
pliris/agents/grounded_orchestrator.py
api/routes/chat.py
tests/unit/test_grounded_persistence.py
tests/unit/test_grounded_orchestrator.py
tests/unit/test_chat_route.py
tests/unit/test_retrieval_persistence_metadata.py
tests/integration/test_grounded_persistence.py
README_PHASE_4_STEP_5.md
```

## Transaction contract

One successful interaction is persisted in one PostgreSQL transaction:

```text
conversation
    -> user message
    -> retrieval query
    -> retrieval result rows
    -> assistant message
    -> monitoring event
```

If any database write fails, the transaction is rolled back.

Persistence is deliberately fail-open at the orchestration boundary:

- a valid grounded answer is still returned;
- `metadata.persistence.status` becomes `failed`;
- only the exception type is exposed in response metadata;
- the full persistence exception remains in server logs.

A persistence failure never changes a supported answer into an HTTP 500.

## Conversation identity

The public API continues to use a string conversation/session identifier.

- A supplied identifier is reused through
  `conversations.client_session_id`.
- A database UUID supplied by a backend caller is also recognized.
- When no identifier is supplied, a UUID session string is generated and
  returned to the client.
- A transaction-scoped PostgreSQL advisory lock prevents duplicate
  conversations for concurrent requests using the same client session.

## Retrieval audit fidelity

`HostedHybridRetriever` now preserves the hosted RPC's:

```text
semantic_rank
keyword_rank
```

inside normalized chunk metadata. The persistence repository writes those
values to `retrieval_results`.

`selected_for_context` reflects every chunk placed in the assembled prompt
context, not only chunks cited in the final answer.

## Pre-extraction

Confirm the branch is clean and remove the diagnostic audit:

```bash
git status --short
git --no-pager log -4 --oneline
rm -f phase4_step5_persistence_audit.txt
```

Expected recent commit:

```text
e7f05c1 chore: isolate TestClient dependency
```

Extract this package into the repository root while remaining on:

```text
feature-grounded-response-pipeline
```

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_grounded_persistence.py \
  tests/unit/test_grounded_orchestrator.py \
  tests/unit/test_chat_route.py \
  tests/unit/test_retrieval_persistence_metadata.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
27 passed
```

Expected approximate totals:

```text
103 passed, 13 deselected
13 passed, 103 deselected
```

The integration persistence test creates and deletes its own records and does
not call OpenAI.

## Live API and persistence smoke test

This performs scope classification, hosted retrieval, grounded generation, and
database persistence. It makes paid OpenAI calls and cleans up its test rows.

```bash
uv run python - <<'PY'
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.chat import router
from pliris.database.postgres import (
    close_postgres_pool,
    postgres_connection,
)


session_id = f"persistence-smoke-{uuid4()}"

app = FastAPI()
app.include_router(router, prefix="/chat")
client = TestClient(app)

response = client.post(
    "/chat/",
    json={
        "message": "What is requirements traceability?",
        "conversation_id": session_id,
        "context": {"document_id": "babok-v3"},
    },
)
response.raise_for_status()
payload = response.json()
persistence = payload["metadata"]["persistence"]

print("status:", response.status_code)
print("conversation_id:", payload["conversation_id"])
print("persistence:", persistence)

assert payload["conversation_id"] == session_id
assert persistence["status"] == "completed"
assert persistence["retrieval_result_count"] == 5

try:
    with postgres_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select count(*) as count
                from public.messages
                where conversation_id = %s
                """,
                (persistence["database_conversation_id"],),
            )
            print("messages:", cursor.fetchone()["count"])

            cursor.execute(
                """
                select count(*) as count
                from public.retrieval_results
                where retrieval_query_id = %s
                """,
                (persistence["retrieval_query_id"],),
            )
            print("retrieval_results:", cursor.fetchone()["count"])

            cursor.execute(
                """
                select event_type
                from public.monitoring_events
                where id = %s
                """,
                (persistence["monitoring_event_id"],),
            )
            print("event:", cursor.fetchone()["event_type"])
finally:
    with postgres_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                delete from public.monitoring_events
                where id = %s
                """,
                (persistence["monitoring_event_id"],),
            )
            cursor.execute(
                """
                delete from public.retrieval_queries
                where id = %s
                """,
                (persistence["retrieval_query_id"],),
            )
            cursor.execute(
                """
                delete from public.conversations
                where id = %s
                """,
                (persistence["database_conversation_id"],),
            )
        connection.commit()

    close_postgres_pool()
PY
```

Expected record counts:

```text
messages: 2
retrieval_results: 5
event: grounded_response_completed
```

## Review checkpoints

Before committing, confirm:

- one conversation contains one user and one assistant message;
- the retrieval query references the user message;
- all retrieved chunks are recorded;
- semantic and keyword ranks are populated where returned by the RPC;
- selected context rows have `selected_for_context = true`;
- the assistant message stores citations, model name, tokens, and latency;
- the monitoring event references the assistant message;
- a persistence failure test still returns the valid answer;
- the diagnostic audit file is not staged.

## Commit

```bash
git status --short

git add \
  README_PHASE_4_STEP_5.md \
  api/routes/chat.py \
  pliris/agents/grounded_orchestrator.py \
  pliris/database/repositories/grounded_persistence.py \
  pliris/retrieval/hosted_hybrid.py \
  tests/unit/test_grounded_persistence.py \
  tests/unit/test_grounded_orchestrator.py \
  tests/unit/test_chat_route.py \
  tests/unit/test_retrieval_persistence_metadata.py \
  tests/integration/test_grounded_persistence.py

git --no-pager diff --cached --stat
git --no-pager diff --cached --check

git commit -m "feat: persist grounded response pipeline"
git push
```

## Known schema-hygiene follow-up

The audit also found that `supabase/seed.sql` and
`supabase/tests/database_tests.sql` still reference obsolete table and column
names. They are not used by this persistence path and are intentionally not
mixed into this increment.

They should be corrected in the next small database-hygiene increment before a
local `supabase db reset` or database SQL-test workflow is treated as
reproducible.
