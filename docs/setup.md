# Setup and clean-machine reproduction

## Requirements

- Git
- Docker Desktop or Docker Engine with Compose v2
- OpenAI API key
- Supabase project with Postgres, Data API, and Storage
- Optional local workflow: Python 3.12 and uv 0.11.30

## Configure hosted services

Create a Supabase project and apply the SQL files in `supabase/migrations/` in filename order. Create
the private Storage bucket named by `SUPABASE_STORAGE_BUCKET`. Copy `.env.example` to `.env` and
replace every placeholder. The current names are `SUPABASE_PUBLISHABLE_KEY`,
`SUPABASE_SECRET_KEY`, `SUPABASE_DB_URL`, `OPENAI_API_KEY`, `GUEST_UI_SHARED_SECRET`, and
`DEVELOPER_UI_ACCESS_KEY`.

Do not put credentials in screenshots, reports, committed files, browser URLs, or client-side code.

## Reproduce with Docker Compose

From a clean checkout:

```bash
cp .env.example .env
# Configure .env.
docker compose config --quiet
docker compose --profile developer up --build --wait
docker compose ps
curl --fail http://localhost:8000/health/live
curl --fail http://localhost:8000/health/ready
```

| Service | Port | Purpose |
|---|---:|---|
| `api` | 8000 | FastAPI and OpenAPI docs |
| `streamlit` | 8501 | Public chat only |
| `streamlit-developer` | 8502 | Protected developer workspace |

Compose waits for the API health check before starting either UI. Containers run as the non-root
`pliris` user with dropped Linux capabilities and `no-new-privileges`.

## Reproduce the quality gate locally

```bash
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run pytest -q -m "not integration"
uv run python -m scripts.verify_environment
```

Integration tests require configured hosted services and are intentionally excluded from offline CI:

```bash
uv run pytest -q -m integration
```

## Reproduce the public corpus

```bash
uv run python -m scripts.build_sample_corpus
cp data/sample/Pliris_Public_BA_Primer.pdf data/private/
uv run python -m scripts.ingest_document --document-id pliris-public-ba-primer --dry-run
```

Do not copy or commit private source material into `data/sample`.

## Troubleshooting

- Import errors: run from the repository root using `uv run`, not from a patch directory.
- Readiness 503: confirm Supabase URLs, keys, database URL, and migrations.
- Developer UI denied: use the value of `DEVELOPER_UI_ACCESS_KEY` at `localhost:8502`.
- Port conflict: stop the existing process or change the left side of the port mapping in Compose.
- Reset: `docker compose --profile developer down`; add `--volumes` only when intentional.
