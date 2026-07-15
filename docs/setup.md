# Setup Guide

## Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for production deployment)
- Supabase account and project
- OpenAI API key

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pliris-ba-bot
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
make install
# or
pip install -e ".[dev]"
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Supabase
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
SUPABASE_ANON_KEY=your_supabase_anon_key

# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/pliris
```

### 5. Set Up Database

#### Option A: Using Supabase Dashboard

1. Go to your Supabase project dashboard
2. Navigate to SQL Editor
3. Run the migration file: `supabase/migrations/202607120001_initial_pliris_schema.sql`
4. Run the seed file: `supabase/seed.sql`

#### Option B: Using Script

```bash
make db-setup
# or
python scripts/check_supabase.py
```

### 6. Verify Environment

```bash
python scripts/verify_environment.py
```

## Running the Application

### Development Mode

```bash
make dev
```

This starts:
- FastAPI backend on http://localhost:8000
- Streamlit UI on http://localhost:8501

### Production Mode

```bash
make prod
```

This starts Docker containers for:
- API server
- Streamlit UI
- PostgreSQL database

### Individual Components

#### Start API only

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Start Streamlit only

```bash
streamlit run app/Home.py --server.address 0.0.0.0 --server.port 8501
```

## Document Ingestion

### Ingest a Single Document

```bash
python scripts/ingest_documents.py path/to/document.pdf
```

### Ingest a Directory

```bash
python scripts/ingest_documents.py path/to/documents/
```

### Using the Ingestion Pipeline Directly

```bash
python -m ingestion.run path/to/document.pdf
```

## Testing

### Run All Tests

```bash
make test
# or
pytest tests/
```

### Run Unit Tests Only

```bash
pytest tests/unit/
```

### Run Integration Tests Only

```bash
pytest tests/integration/
```

### Run with Coverage

```bash
pytest --cov=pliris --cov=api --cov=app
```

## Code Quality

### Linting

```bash
make lint
# or
ruff check .
mypy pliris api app
```

### Formatting

```bash
make format
# or
black .
ruff check --fix .
```

## Troubleshooting

### Database Connection Issues

1. Verify DATABASE_URL in `.env`
2. Check Supabase project status
3. Run `python scripts/check_supabase.py`

### OpenAI API Issues

1. Verify OPENAI_API_KEY in `.env`
2. Check API key has sufficient credits
3. Verify model availability in your region

### Import Errors

1. Ensure virtual environment is activated
2. Reinstall dependencies: `pip install -e .`
3. Check Python version (3.11+)

### Port Already in Use

Change ports in `.env`:
```env
API_PORT=8001
STREAMLIT_PORT=8502
```

## Next Steps

1. Ingest your documents
2. Test the chat interface
3. Run evaluation scripts
4. Configure monitoring
5. Set up production deployment

See [Usage Guide](usage.md) for more information on using the application.
