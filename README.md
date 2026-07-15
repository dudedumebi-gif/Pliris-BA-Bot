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

### Ingesting Documents

```bash
python scripts/ingest_documents.py --path data/private/
```

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
