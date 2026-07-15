"""Index document chunks in the database."""

import logging
import uuid

from pliris.database.supabase_client import get_client

logger = logging.getLogger(__name__)


async def index_chunks_in_database(chunks: list[dict]) -> list[str]:
    """
    Index document chunks in the database.

    Args:
        chunks: List of chunk dictionaries with embeddings

    Returns:
        List of chunk IDs
    """
    if not chunks:
        return []

    try:
        client = get_client()
        chunk_ids = []

        for chunk in chunks:
            try:
                # Generate chunk ID
                chunk_id = str(uuid.uuid4())

                # Prepare chunk data
                chunk_data = {
                    "id": chunk_id,
                    "text": chunk["text"],
                    "embedding": chunk["embedding"],
                    "source": chunk["metadata"].get("source", "unknown"),
                    "title": chunk["metadata"].get("title", "unknown"),
                    "page": chunk["metadata"].get("page"),
                    "chunk_index": chunk["chunk_index"],
                    "metadata": chunk["metadata"],
                }

                # Insert into database
                client.table("chunks").insert(chunk_data).execute()

                chunk_ids.append(chunk_id)

                logger.debug(f"Indexed chunk {chunk.get('chunk_index', 'unknown')}")

            except Exception as e:
                logger.error(f"Error indexing chunk: {e}")
                continue

        logger.info(f"Indexed {len(chunk_ids)} chunks in database")

        return chunk_ids

    except Exception as e:
        logger.error(f"Error indexing chunks in database: {e}", exc_info=True)
        raise


async def delete_chunks_from_database(chunk_ids: list[str]) -> bool:
    """
    Delete chunks from the database.

    Args:
        chunk_ids: List of chunk IDs to delete

    Returns:
        True if successful
    """
    try:
        client = get_client()

        # Delete chunks
        client.table("chunks").delete().in_("id", chunk_ids).execute()

        logger.info(f"Deleted {len(chunk_ids)} chunks from database")

        return True

    except Exception as e:
        logger.error(f"Error deleting chunks from database: {e}", exc_info=True)
        return False


async def get_chunks_by_document(document_id: str) -> list[dict]:
    """
    Get all chunks for a document.

    Args:
        document_id: Document ID

    Returns:
        List of chunk dictionaries
    """
    try:
        client = get_client()

        response = client.table("chunks").select("*").eq("document_id", document_id).execute()

        return response.data or []

    except Exception as e:
        logger.error(f"Error getting chunks for document: {e}", exc_info=True)
        return []
