import logging

logger = logging.getLogger(__name__)


class Reranker:
    """Rerank search results using Cohere's rerank API."""

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Cohere client."""
        try:
            # Cohere API key would be in settings
            # self.client = cohere.Client(settings.cohere_api_key)
            logger.info("Cohere rerank client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Cohere client: {e}")

    async def rerank(self, query: str, results: list[dict], top_k: int = 5) -> list[dict]:
        """
        Rerank search results.

        Args:
            query: Original query
            results: Search results to rerank
            top_k: Number of results to return

        Returns:
            Reranked list of results
        """
        if not results:
            return results

        try:
            # If Cohere client is not available, return original results
            if self.client is None:
                logger.info("Using original results (reranker not available)")
                return results[:top_k]

            # Prepare documents for reranking
            documents = [result["text"] for result in results]

            # Rerank using Cohere
            rerank_results = self.client.rerank(
                model="rerank-english-v2.0", query=query, documents=documents, top_n=top_k
            )

            # Reorder results based on rerank scores
            reranked = []
            for result in rerank_results.results:
                original_result = results[result.index].copy()
                original_result["score"] = result.relevance_score
                reranked.append(original_result)

            return reranked

        except Exception as e:
            logger.error(f"Error in reranking: {e}", exc_info=True)
            # Return original results on error
            return results[:top_k]
