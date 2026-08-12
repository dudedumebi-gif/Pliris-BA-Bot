# Phase 7 Step 1D — Session-Owned Conversation Continuation

## Defect found by browser smoke testing

The first grounded answer worked, but a follow-up such as:

`Give me a practical example based on the explanation you just provided.`

was classified in isolation and returned the out-of-scope response. The
production grounded pipeline used `conversation_id` only as a persistence key;
it did not load prior messages for classification, retrieval, or generation.

## Correction

- New conversation identifiers are opaque HMAC-signed tokens.
- Each token is cryptographically bound to one anonymous browser session.
- Tokens presented by another guest session are rejected before database reads.
- A bounded six-message history is loaded by the validated token.
- Explicit context-dependent follow-ups are resolved deterministically.
- No additional LLM call is introduced for query rewriting.
- Scope classification, retrieval, and generation use the resolved question.
- Persistence continues to store the user's original message.
- The grounded generator and citation-validation contract remain unchanged.
- Standalone unrelated questions are not forced into earlier context.
- Valid inline citations are canonical when the model's redundant `citation_ids` list differs; unknown, malformed, and missing inline citations still fail validation.
- Citation-list normalization is recorded in response metadata for developer inspection and EvalOps.
- Failed API turns are removed from Streamlit session history so a manual retry does not duplicate the user question.

## Security properties

The conversation token does not contain credentials or raw session identifiers.
The API signs tokens with `GUEST_UI_SHARED_SECRET` in configured deployments. In
local development without that value, a process-local random secret is used;
tokens then become invalid after an API restart.

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest \
  tests/unit/test_conversation_tokens.py \
  tests/unit/test_conversation_context.py \
  tests/unit/test_conversation_history.py \
  tests/unit/test_chat_continuation.py \
  tests/unit/test_chat_route.py \
  -q
uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```
