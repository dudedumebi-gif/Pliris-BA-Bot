"""Main entry point for the ingestion pipeline."""

import asyncio
import logging
from pathlib import Path

from ingestion.chunk_documents import chunk_document
from ingestion.clean_text import clean_document_text
from ingestion.extract_pdf import extract_text_from_pdf
from ingestion.generate_embeddings import generate_chunk_embeddings
from ingestion.index_chunks import index_chunks_in_database
from ingestion.manifest import update_manifest
from ingestion.upload_storage import upload_to_storage

logger = logging.getLogger(__name__)


async def process_document(file_path: str, metadata: dict) -> dict:
    """
    Process a single document through the entire ingestion pipeline.

    Args:
        file_path: Path to the document file
        metadata: Document metadata

    Returns:
        Processing results
    """
    try:
        logger.info(f"Processing document: {file_path}")

        # Step 1: Extract text
        logger.info("Extracting text...")
        text = extract_text_from_pdf(file_path)

        # Step 2: Clean text
        logger.info("Cleaning text...")
        cleaned_text = clean_document_text(text)

        # Step 3: Chunk document
        logger.info("Chunking document...")
        chunks = chunk_document(cleaned_text, metadata)

        # Step 4: Generate embeddings
        logger.info("Generating embeddings...")
        chunks_with_embeddings = await generate_chunk_embeddings(chunks)

        # Step 5: Upload to storage
        logger.info("Uploading to storage...")
        storage_path = await upload_to_storage(file_path)

        # Step 6: Index in database
        logger.info("Indexing in database...")
        chunk_ids = await index_chunks_in_database(chunks_with_embeddings)

        # Step 7: Update manifest
        logger.info("Updating manifest...")
        await update_manifest(
            {
                **metadata,
                "file_path": storage_path,
                "chunk_count": len(chunks),
                "chunk_ids": chunk_ids,
                "status": "indexed",
            }
        )

        logger.info(f"Successfully processed document: {file_path}")

        return {
            "status": "success",
            "file_path": file_path,
            "storage_path": storage_path,
            "chunk_count": len(chunks),
            "chunk_ids": chunk_ids,
        }

    except Exception as e:
        logger.error(f"Error processing document {file_path}: {e}", exc_info=True)
        return {"status": "error", "file_path": file_path, "error": str(e)}


async def process_directory(directory: str) -> list:
    """
    Process all documents in a directory.

    Args:
        directory: Path to directory containing documents

    Returns:
        List of processing results
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        logger.error(f"Directory does not exist: {directory}")
        return []

    # Find all PDF files
    pdf_files = list(dir_path.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"No PDF files found in {directory}")
        return []

    logger.info(f"Found {len(pdf_files)} PDF files to process")

    results = []
    for pdf_file in pdf_files:
        metadata = {"title": pdf_file.stem, "source": "unknown", "type": "document"}

        result = await process_document(str(pdf_file), metadata)
        results.append(result)

    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        path = sys.argv[1]
        if Path(path).is_dir():
            asyncio.run(process_directory(path))
        else:
            asyncio.run(process_document(path, {}))
    else:
        print("Usage: python run.py <file_or_directory>")
