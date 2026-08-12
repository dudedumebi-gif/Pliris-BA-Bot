# Pliris BA Bot

Pliris is a production-oriented, domain-restricted RAG assistant for Business Analysis, Business
Systems Analysis, and Project Management. It combines grounded generation, hybrid retrieval,
citations, scope and prompt-injection guardrails, feedback, and protected operational monitoring.

## Architecture

- FastAPI backend with public liveness/readiness and protected diagnostics
- Separate Streamlit public (`8501`) and developer (`8502`) interfaces
- Supabase Postgres, vector search, Data API, and private object storage
- OpenAI chat and embedding models
- Hybrid lexical/vector retrieval with optional reranking

See [architecture](docs/architecture.md) for component and request-flow details.

## Quick start

Prerequisites: Git, Docker Desktop with Compose v2, and credentials for OpenAI and Supabase.

```bash
git clone https://github.com/dudedumebi-gif/Pliris-BA-Bot.git
cd Pliris-BA-Bot
cp .env.example .env
# Fill in .env; never commit it.
docker compose --profile developer up --build --wait
```

Open the public chat at <http://localhost:8501>, the protected developer interface at
<http://localhost:8502>, and API docs at <http://localhost:8000/docs>. Stop everything with:

```bash
docker compose --profile developer down
```

For a local Python workflow, install Python 3.12 and uv 0.11.30, then run `uv sync --frozen`.
The exact dependency graph is committed in `uv.lock`.

## Verify

```bash
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run pytest -q -m "not integration"
docker compose config --quiet
```

Every pull request to `main` also runs CodeQL for Python and Trivy against the repository and final
container image. The workflow retains JSON, SARIF, CycloneDX SBOMs, and a commit-addressed audit
summary. See [security](docs/security.md).

## Public sample corpus

`data/sample/Pliris_Public_BA_Primer.pdf` is an original, redistributable document that lets a
reviewer exercise PDF extraction and ingestion without the private BABOK corpus. Rebuild it with:

```bash
uv run python -m scripts.build_sample_corpus
```

Register or stage only documents declared in `data/corpus_manifest.yaml`. The protected developer
Sources workspace validates uploads, rejects duplicates, stores accepted PDFs privately, and
creates a pending record. See [ingestion](docs/ingestion.md).

## Documentation

- [Setup and clean-machine reproduction](docs/setup.md)
- [Usage and protected interfaces](docs/usage.md)
- [Reviewer walkthrough](docs/walkthrough.md)
- [Security and CVE evidence](docs/security.md)
- [Evaluation](docs/evaluation.md)
- [Monitoring](docs/monitoring.md)
- [Submission audit](docs/submission-audit.md)

## License

MIT. Private knowledge-base sources are excluded from the repository and are not covered by the
software license.
