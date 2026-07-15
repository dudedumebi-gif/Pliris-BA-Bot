import logging

from pliris.database.supabase_client import get_client
from pliris.generation.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Semantic search using vector embeddings."""

    def __init__(self):
        self.embedding_client = OpenAIClient()
        self.supabase = get_client()

    async def search(
        self, query: str, top_k: int = 10, filters: dict | None = None
    ) -> list[dict]:
        """
        Perform semantic search using vector similarity.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters for search

        Returns:
            List of retrieved chunks with scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.get_embedding(query)

            # Search in Supabase
            response = self.supabase.rpc(
                "match_documents",
                {"query_embedding": query_embedding, "match_count": top_k, "filter": filters or {}},
            )

            results = response.data or []

            # Format results
            formatted = []
            for result in results:
                formatted.append(
                    {
                        "id": result.get("id"),
                        "text": result.get("text"),
                        "source": result.get("source"),
                        "title": result.get("title"),
                        "page": result.get("page"),
                        "score": result.get("similarity", 0.0),
                        "metadata": result.get("metadata", {}),
                    }
                )

            return formatted

        except Exception as e:
            logger.error(f"Error in semantic search: {e}", exc_info=True)
            return []
