# Pliris BA Bot

A Business Analyst AI assistant powered by RAG (Retrieval-Augmented Generation) with guardrails and monitoring capabilities.

## Architecture

This project uses a modern architecture with:
- **Streamlit** for the user interface
- **FastAPI** for the backend API
- **Supabase** for database and storage
- **OpenAI** for LLM and embeddings
- **Hybrid search** (semantic + lexical) for retrieval

## Project Structure

```
pliris-ba-bot/
├── app/                    # Streamlit UI
├── api/                    # FastAPI backend
├── pliris/                 # Core application package
├── ingestion/              # Document ingestion pipeline
├── evaluation/             # Retrieval and LLM evaluation
├── supabase/               # Database migrations and config
├── data/                   # Data directories
├── scripts/                # Utility scripts
├── tests/                  # Unit and integration tests
└── docs/                   # Documentation
```

## Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Supabase account
- OpenAI API key

### Installation

1. Clone the repository and navigate to the project directory
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` with your configuration values
4. Install dependencies:
   ```bash
   make install
   ```
5. Set up the database:
   ```bash
   make db-setup
   ```
6. Run the application:
   ```bash
   make dev
   ```

## Usage

### Starting the Application

- **Development mode**: `make dev` (starts API and Streamlit)
- **Production mode**: `make prod` (uses Docker Compose)

### Guarded PDF Staging and Ingestion

Documents must first be registered in `data/corpus_manifest.yaml`. The protected
developer Sources workspace validates uploaded PDFs, rejects duplicate checksums,
stores accepted files privately, and creates a non-retrievable `pending` record.

Inspect extraction and chunking without database writes or embeddings:

```bash
uv run python -m scripts.ingest_document \
  --document-id MANIFEST_ID \
  --dry-run
```

Ingest one exact staged document:

```bash
uv run python -m scripts.ingest_document \
  --document-id MANIFEST_ID \
  --staged-document-id DATABASE_DOCUMENT_UUID
```

Replace `MANIFEST_ID` and `DATABASE_DOCUMENT_UUID` with real values before
running these commands.

The staged handoff verifies the document UUID, manifest ID, checksum, storage
location, `pending` status, and absence of existing chunks before embedding.
`--force` cannot be combined with `--staged-document-id`. A successfully
indexed document is persisted with status `ready`.

#### Phase 7 Step 2C Acceptance

Commit `05b692f` completed the guarded staging-to-ingestion workflow. The
controlled GAO Agile Assessment Guide acceptance processed 324 pages into
204 fully embedded chunks with no ingestion error. The final document status
was `ready`. BABOK (`babok-v3`) remained untouched.

### Running Evaluations

```bash
python evaluation/retrieval_eval.py
python evaluation/llm_eval.py
python evaluation/scope_eval.py
```

## Documentation

- [Architecture](docs/architecture.md)
- [Setup](docs/setup.md)
- [Usage](docs/usage.md)
- [Ingestion](docs/ingestion.md)
- [Evaluation](docs/evaluation.md)
- [Monitoring](docs/monitoring.md)

## Makefile Commands

- `make install` - Install dependencies
- `make dev` - Start development servers
- `make prod` - Start production containers
- `make db-setup` - Set up database
- `make test` - Run tests
- `make lint` - Run linting
- `make format` - Format code

## License

MIT
