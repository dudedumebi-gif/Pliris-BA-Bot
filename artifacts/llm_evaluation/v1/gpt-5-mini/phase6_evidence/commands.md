# Phase 6 Reproducibility Commands

All commands run from the repository root.

## Inspect the frozen primary plan

```bash
uv run python -m scripts.evaluate_llm_prompts --plan
```

## Prepare contexts

```bash
uv run python -m scripts.evaluate_llm_prompts \
  --prepare-contexts \
  --embedding-input-price-per-million <CURRENT_RATE>
```

## Run the primary comparison

```bash
uv run python -m scripts.evaluate_llm_prompts \
  --execute \
  --generation-input-price-per-million <CURRENT_INPUT_RATE> \
  --generation-output-price-per-million <CURRENT_OUTPUT_RATE>
```

## Prepare and finalize the primary blinded review

```bash
uv run python -m scripts.review_llm_prompts --prepare
uv run python -m scripts.review_llm_prompts \
  --finalize \
  --reviewer-id "Dums"
```

## Inspect and run the finalist confirmation

```bash
uv run python -m scripts.confirm_llm_finalists --plan
uv run python -m scripts.confirm_llm_finalists \
  --execute \
  --generation-input-price-per-million <CURRENT_INPUT_RATE> \
  --generation-output-price-per-million <CURRENT_OUTPUT_RATE>
```

## Prepare and finalize the finalist diagnostic review

```bash
uv run python -m scripts.review_llm_finalists --prepare
uv run python -m scripts.review_llm_finalists \
  --finalize \
  --reviewer-id "Dums"
```

The recorded first-run outputs must not be regenerated or replaced. Runtime pricing
placeholders intentionally require current official rates for any future reproduction.
