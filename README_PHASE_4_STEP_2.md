# Phase 4 Step 2 - Grounded Responses API Generation

This increment builds a validated answer-generation contract on top of the
hosted retrieval and context assembly introduced in Phase 4 Step 1.

It does not yet replace the existing agent orchestrator, FastAPI route,
Streamlit UI, evidence checker, or persistence repositories.

## Files

```text
pliris/generation/grounded_models.py
pliris/generation/citation_validator.py
pliris/generation/grounded_generator.py
scripts/generate_grounded_answer.py
tests/unit/test_citation_validator.py
tests/unit/test_grounded_generator.py
README_PHASE_4_STEP_2.md
```

## Behaviour

`GroundedResponseGenerator`:

- uses the OpenAI Responses API;
- uses the configured Pliris chat model by default;
- sends the assembled knowledge-base context as the only evidence source;
- requests strict JSON-schema output;
- disables response storage for this request path;
- records response ID, model, and token usage;
- returns the approved insufficient-evidence response without an API call when
  no context sources are available.

`CitationValidator`:

- accepts exact citation identifiers such as `[S1]`;
- rejects unknown or malformed source identifiers;
- rejects mismatches between inline citations and `citation_ids`;
- maps cited identifiers to the source metadata created by
  `ContextAssembler`;
- applies an exact insufficient-evidence fallback contract.

## Extract

Remain on:

```text
feature-grounded-response-pipeline
```

Before extraction, inspect the unrelated modified file shown after the Step 1
commit:

```bash
git --no-pager diff -- README_PHASE_3_STEP_4.md
```

When that modification is accidental, restore it:

```bash
git restore README_PHASE_3_STEP_4.md
```

Do not include an unrelated Phase 3 README modification in the Step 2 commit.

Extract the package into the repository root. All packaged files are new.

## Quality gate

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .

uv run pytest \
  tests/unit/test_citation_validator.py \
  tests/unit/test_grounded_generator.py \
  -v

uv run pytest -m "not integration" -q
uv run pytest -m integration -q
```

Expected focused count:

```text
12 passed
```

The non-integration count should increase from 64 to approximately 76. The
integration count should remain 12.

## Live paid smoke test

This command performs hosted retrieval and one paid OpenAI generation call:

```bash
uv run python -m scripts.generate_grounded_answer \
  "What is requirements traceability?" \
  --document-id babok-v3 \
  --top-k 5
```

Expected result characteristics:

- `retrieved_count` is 5;
- the answer uses only identifiers present in `result.citation_ids`;
- each citation maps to a source in `result.citations`;
- the answer contains inline forms such as `[S1]`;
- `insufficient_evidence` is false;
- `usage` contains token counts when returned by the API;
- `store` is disabled in the Responses API request.

Also test deterministic insufficient evidence without incurring an API call:

```bash
uv run python - <<'PY'
import asyncio

from pliris.generation.context_assembler import ContextAssembler
from pliris.generation.grounded_generator import (
    GroundedResponseGenerator,
)


async def main() -> None:
    context = ContextAssembler().assemble([])
    answer = await GroundedResponseGenerator().generate(
        question="What is not covered by the knowledge base?",
        context=context,
    )
    print(answer.to_dict())


asyncio.run(main())
PY
```

## Review checkpoints

Before committing, confirm:

- valid source identifiers map to the correct page metadata;
- unknown source identifiers fail closed;
- empty context skips the paid generation call;
- the exact insufficient-evidence message is preserved;
- no API, UI, orchestrator, or database repository file changed;
- all existing tests continue to pass.

## Commit

```bash
git status --short

git add \
  README_PHASE_4_STEP_2.md \
  pliris/generation/grounded_models.py \
  pliris/generation/citation_validator.py \
  pliris/generation/grounded_generator.py \
  scripts/generate_grounded_answer.py \
  tests/unit/test_citation_validator.py \
  tests/unit/test_grounded_generator.py

git --no-pager diff --cached --stat

git commit -m "feat: add grounded response generation"
git push
```

## Next increment

Phase 4 Step 3 will connect the production hosted retriever, context assembler,
and grounded generator through a new orchestrator contract. That step will
still use injected repositories first, before database persistence is
implemented.
