"""Generate embeddings for document chunks."""

import logging

from pliris.generation.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


async def generate_chunk_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Generate embeddings for document chunks.

    Args:
        chunks: List of chunk dictionaries

    Returns:
        List of chunks with embeddings added
    """
    if not chunks:
        return chunks

    try:
        embedding_client = OpenAIClient()

        chunks_with_embeddings = []

        for chunk in chunks:
            try:
                # Generate embedding for chunk text
                embedding = await embedding_client.get_embedding(chunk["text"])

                # Add embedding to chunk
                chunk_with_embedding = {**chunk, "embedding": embedding}

                chunks_with_embeddings.append(chunk_with_embedding)

                logger.debug(f"Generated embedding for chunk {chunk.get('chunk_index', 'unknown')}")

            except Exception as e:
                logger.error(f"Error generating embedding for chunk: {e}")
                # Add chunk without embedding
                chunks_with_embeddings.append(chunk)

        logger.info(f"Generated embeddings for {len(chunks_with_embeddings)} chunks")

        return chunks_with_embeddings

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}", exc_info=True)
        # Return original chunks on error
        return chunks


async def generate_embedding_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors
    """
    try:
        embedding_client = OpenAIClient()

        embeddings = []
        for text in texts:
            embedding = await embedding_client.get_embedding(text)
            embeddings.append(embedding)

        return embeddings

    except Exception as e:
        logger.error(f"Error generating batch embeddings: {e}", exc_info=True)
        raise
