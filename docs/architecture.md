# Architecture

## Overview

Pliris BA Bot is a RAG (Retrieval-Augmented Generation) system designed for business analysis tasks. The architecture consists of several interconnected components:

## System Architecture

```
┌─────────────────┐
│   Streamlit UI  │
│   (app/)        │
└────────┬────────┘
         │ HTTP
┌────────▼────────┐
│   FastAPI       │
│   Backend       │
│   (api/)        │
└────────┬────────┘
         │
    ┌────┴────┬──────────┬──────────┐
    │         │          │          │
┌───▼───┐ ┌──▼────┐ ┌──▼────┐ ┌──▼────┐
│ Supa- │ │ OpenAI│ │ Agent │ │Guard- │
│ base  │ │ LLM   │ │ Orch. │ │ rails │
└───────┘ └───────┘ └───────┘ └───────┘
```

## Components

### 1. Streamlit UI (`app/`)
- **Home.py**: Main landing page with navigation
- **pages/**: Multi-page application
  - Chat: Conversational interface
  - Sources: Document management
  - Feedback: User feedback collection
  - Monitoring: System metrics dashboard
- **components/**: Reusable UI components
  - chat_message.py: Message rendering
  - citations.py: Citation display
  - feedback.py: Feedback forms

### 2. FastAPI Backend (`api/`)
- **main.py**: Application entry point
- **routes/**: API endpoints
  - chat.py: Chat processing
  - sources.py: Document management
  - feedback.py: Feedback collection
  - monitoring.py: Metrics and events
  - health.py: Health checks
- **schemas/**: Pydantic models for request/response validation
- **middleware.py**: Logging and CORS
- **dependencies.py**: Authentication and database sessions

### 3. Core Package (`pliris/`)

#### Config (`config/`)
- **settings.py**: Environment-based configuration
- **logging.py**: Structured logging setup

#### Database (`database/`)
- **supabase_client.py**: Supabase client wrapper
- **postgres.py**: PostgreSQL connection management
- **repositories/**: Data access layer
  - documents.py: Document CRUD
  - conversations.py: Conversation management
  - feedback.py: Feedback storage
  - monitoring.py: Event logging

#### Agents (`agents/`)
- **ba_agent.py**: Business analyst agent
- **orchestrator.py**: Query processing pipeline
- **tools.py**: Agent tool registry

#### Retrieval (`retrieval/`)
- **semantic_search.py**: Vector-based search
- **lexical_search.py**: BM25 keyword search
- **hybrid_search.py**: Combined semantic + lexical
- **reranker.py**: Result reranking
- **query_rewriter.py**: Query optimization

#### Generation (`generation/`)
- **openai_client.py**: OpenAI API client
- **prompts.py**: Prompt templates
- **response_builder.py**: Response formatting
- **citations.py**: Citation extraction and formatting

#### Guardrails (`guardrails/`)
- **scope_classifier.py**: Query scope classification
- **prompt_injection.py**: Prompt injection detection
- **evidence_checker.py**: Evidence validation
- **response_guardrail.py**: Response filtering

#### Monitoring (`monitoring/`)
- **events.py**: Event logging
- **metrics.py**: Metrics collection
- **dashboard_queries.py**: Dashboard data queries

#### Utils (`utils/`)
- **hashing.py**: Hash generation
- **text.py**: Text processing utilities
- **timing.py**: Performance timing

### 4. Ingestion Pipeline (`ingestion/`)
- **run.py**: Pipeline orchestration
- **extract_pdf.py**: PDF text extraction
- **clean_text.py**: Text cleaning
- **chunk_documents.py**: Document chunking
- **generate_embeddings.py**: Embedding generation
- **upload_storage.py**: Storage upload
- **index_chunks.py**: Database indexing
- **manifest.py**: Document tracking

### 5. Evaluation (`evaluation/`)
- **datasets/**: Evaluation datasets
- **retrieval_eval.py**: Retrieval performance evaluation
- **llm_eval.py**: LLM response quality evaluation
- **scope_eval.py**: Guardrail evaluation
- **metrics.py**: Evaluation metrics

### 6. Database (`supabase/`)
- **migrations/**: Database schema migrations
- **seed.sql**: Seed data
- **config.toml**: Supabase configuration

## Data Flow

### Query Processing Pipeline

1. **User Query** → Streamlit UI
2. **HTTP Request** → FastAPI Backend
3. **Guardrails Check** → Scope classifier, prompt injection detection
4. **Query Rewriting** → Optimize for retrieval
5. **Hybrid Search** → Semantic + lexical retrieval
6. **Reranking** → Improve result relevance
7. **Response Generation** → LLM with retrieved context
8. **Evidence Checking** → Validate response accuracy
9. **Response Guardrails** → Filter harmful content
10. **Response** → Streamlit UI with citations

### Document Ingestion Pipeline

1. **Upload** → User uploads document
2. **Extraction** → Extract text from PDF/DOCX
3. **Cleaning** → Normalize and clean text
4. **Chunking** → Split into manageable chunks
5. **Embedding** → Generate vector embeddings
6. **Storage** → Upload to Supabase Storage
7. **Indexing** → Store chunks with embeddings in database
8. **Manifest Update** → Track document in manifest

## Technology Stack

- **Frontend**: Streamlit
- **Backend**: FastAPI
- **Database**: PostgreSQL with pgvector
- **Storage**: Supabase Storage
- **LLM**: OpenAI GPT-4
- **Embeddings**: OpenAI text-embedding-3-small
- **Reranking**: Cohere Rerank API
- **Search**: Hybrid (semantic + lexical)
- **Monitoring**: Custom event logging

## Security Considerations

- API key authentication (configurable)
- Prompt injection detection
- Scope classification for query filtering
- Response guardrails for content filtering
- PII redaction in responses
- Environment variable management

## Scalability

- Async/await for concurrent processing
- Database connection pooling
- Vector indexing with IVFFlat
- Chunked document processing
- Horizontal scaling via Docker Compose
