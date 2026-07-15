# Document Ingestion Guide

## Overview

The ingestion pipeline processes documents and makes them searchable through the RAG system. The pipeline consists of several stages:

1. **Text Extraction**: Extract text from PDF, DOCX, or TXT files
2. **Text Cleaning**: Normalize and clean the extracted text
3. **Chunking**: Split documents into manageable chunks
4. **Embedding Generation**: Generate vector embeddings for each chunk
5. **Storage Upload**: Upload original files to Supabase Storage
6. **Database Indexing**: Store chunks with embeddings in PostgreSQL

## Running the Ingestion Pipeline

### Command Line

```bash
# Ingest a single document
python scripts/ingest_documents.py path/to/document.pdf

# Ingest a directory of documents
python scripts/ingest_documents.py path/to/documents/

# Using the ingestion module directly
python -m ingestion.run path/to/document.pdf
```

### Python API

```python
import asyncio
from ingestion.run import process_document

async def main():
    result = await process_document(
        file_path="path/to/document.pdf",
        metadata={
            "title": "Annual Report 2024",
            "source": "Finance Department",
            "type": "report",
            "tags": ["finance", "2024"]
        }
    )
    print(result)

asyncio.run(main())
```

## Document Requirements

### Supported Formats

- **PDF**: .pdf files
- **Word Documents**: .docx files
- **Plain Text**: .txt files

### File Size Limits

- Recommended: < 50MB per document
- Maximum: 100MB per document

### Text Quality

- OCR-scanned PDFs may have lower quality
- Tables and complex layouts may not extract perfectly
- Images within documents are not processed

## Configuration

### Chunking Parameters

Edit `.env` or `pliris/config/settings.py`:

```env
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

- **CHUNK_SIZE**: Maximum characters per chunk
- **CHUNK_OVERLAP**: Characters of overlap between chunks

### Embedding Model

```env
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Available models:
- `text-embedding-3-small`: Fast, cost-effective (default)
- `text-embedding-3-large`: Higher quality, slower

## Pipeline Stages

### 1. Text Extraction

Extracts text from documents using:
- **pypdf** for PDF files
- **python-docx** for Word documents
- Built-in for plain text

### 2. Text Cleaning

Normalizes text by:
- Removing excessive whitespace
- Normalizing quotes and dashes
- Removing special characters
- Cleaning headers and footers

### 3. Chunking

Splits documents into chunks:
- Respects paragraph boundaries
- Maintains context with overlap
- Preserves metadata

### 4. Embedding Generation

Creates vector embeddings using OpenAI:
- Each chunk gets a 1536-dimensional vector
- Vectors enable semantic search
- Stored in pgvector column

### 5. Storage Upload

Uploads original files:
- Stored in Supabase Storage
- Organized in buckets
- Accessible for download

### 6. Database Indexing

Stores chunks in database:
- Text content
- Embedding vector
- Source metadata
- Document references

## Monitoring Ingestion

### Progress Tracking

The pipeline logs progress at each stage:
```
Processing document: document.pdf
Extracting text...
Cleaning text...
Chunking document...
Generating embeddings...
Uploading to storage...
Indexing in database...
Updating manifest...
Successfully processed document: document.pdf
```

### Error Handling

Errors are logged with context:
```
Error processing document document.pdf: [error details]
```

### Manifest Tracking

The `data/corpus_manifest.yaml` file tracks:
- All processed documents
- Processing status
- Chunk count
- Storage paths

## Best Practices

### Document Preparation

- Use high-quality PDFs (not scanned images)
- Ensure text is selectable
- Remove sensitive information before upload
- Use consistent naming conventions

### Metadata

Provide accurate metadata:
- **Title**: Descriptive document title
- **Source**: Document author or department
- **Type**: Document category (report, policy, etc.)
- **Tags**: Relevant keywords for filtering

### Batch Processing

Process documents in batches:
- Start with a small test set
- Verify quality before scaling
- Monitor system resources
- Process during off-peak hours

## Troubleshooting

### Extraction Fails

- Verify file format is supported
- Check file is not corrupted
- Try converting to PDF if needed

### Low Quality Text

- Use original PDFs, not OCR scans
- Check for password protection
- Verify text is selectable

### Embedding Errors

- Check OpenAI API key
- Verify API credits available
- Check network connectivity

### Storage Upload Fails

- Verify Supabase credentials
- Check storage bucket exists
- Verify file size limits

### Indexing Slow

- Reduce chunk size
- Process fewer documents at once
- Check database performance
- Verify pgvector extension is enabled

## Advanced Usage

### Custom Chunking

```python
from ingestion.chunk_documents import chunk_document

chunks = chunk_document(
    text=document_text,
    metadata=doc_metadata,
    chunk_size=500,  # Custom size
    chunk_overlap=50  # Custom overlap
)
```

### Custom Cleaning

```python
from ingestion.clean_text import clean_document_text

cleaned = clean_document_text(raw_text)
```

### Direct Database Insertion

```python
from ingestion.index_chunks import index_chunks_in_database

chunk_ids = await index_chunks_in_database(chunks_with_embeddings)
```

## Performance Optimization

### Parallel Processing

Process multiple documents concurrently:
```python
import asyncio

documents = ["doc1.pdf", "doc2.pdf", "doc3.pdf"]
tasks = [process_document(doc, {}) for doc in documents]
results = await asyncio.gather(*tasks)
```

### Batch Embeddings

Generate embeddings in batches:
```python
from ingestion.generate_embeddings import generate_embedding_batch

texts = [chunk['text'] for chunk in chunks]
embeddings = await generate_embedding_batch(texts)
```

### Monitoring Resources

Check system resources during ingestion:
- CPU usage
- Memory usage
- OpenAI API rate limits
- Database connection pool
