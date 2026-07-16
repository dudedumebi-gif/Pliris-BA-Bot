import logging

from pliris.retrieval.lexical_search import LexicalSearch
from pliris.retrieval.semantic_search import SemanticSearch

logger = logging.getLogger(__name__)


class HybridSearch:
    """Hybrid search combining semantic and lexical search."""

    def __init__(self, semantic_weight: float = 0.7, lexical_weight: float = 0.3):
        self.semantic_search = SemanticSearch()
        self.lexical_search = LexicalSearch()
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight

    async def search(self, query: str, top_k: int = 10, filters: dict | None = None) -> list[dict]:
        """
        Perform hybrid search combining semantic and lexical results.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional filters for search

        Returns:
            List of retrieved chunks with combined scores
        """
        try:
            # Get semantic results
            semantic_results = await self.semantic_search.search(
                query=query, top_k=top_k * 2, filters=filters
            )

            # Get lexical results
            lexical_results = await self.lexical_search.search(query=query, top_k=top_k * 2)

            # Combine results using reciprocal rank fusion
            combined = self._combine_results(semantic_results, lexical_results, top_k)

            return combined

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}", exc_info=True)
            return []

    def _combine_results(
        self, semantic_results: list[dict], lexical_results: list[dict], top_k: int
    ) -> list[dict]:
        """Combine semantic and lexical results using weighted scoring."""
        # Create score map
        score_map = {}

        # Add semantic scores
        for result in semantic_results:
            doc_id = result["id"]
            score_map[doc_id] = {
                "result": result,
                "semantic_score": result["score"],
                "lexical_score": 0.0,
            }

        # Add lexical scores
        for result in lexical_results:
            doc_id = result["id"]
            if doc_id in score_map:
                score_map[doc_id]["lexical_score"] = result["score"]
            else:
                score_map[doc_id] = {
                    "result": result,
                    "semantic_score": 0.0,
                    "lexical_score": result["score"],
                }

        # Calculate combined scores
        combined_results = []
        for data in score_map.values():
            combined_score = (
                self.semantic_weight * data["semantic_score"]
                + self.lexical_weight * data["lexical_score"]
            )

            result = data["result"].copy()
            result["score"] = combined_score
            combined_results.append(result)

        # Sort by combined score and return top-k
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        return combined_results[:top_k]
