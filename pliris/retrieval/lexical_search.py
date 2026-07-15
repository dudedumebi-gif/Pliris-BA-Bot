import logging
import re

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class LexicalSearch:
    """Lexical search using BM25."""

    def __init__(self):
        self.index = None
        self.documents = []
        self._index_built = False

    def build_index(self, documents: list[dict]):
        """Build BM25 index from documents."""
        try:
            self.documents = documents
            tokenized_docs = [self._tokenize(doc["text"]) for doc in documents]
            self.index = BM25Okapi(tokenized_docs)
            self._index_built = True
            logger.info(f"Built lexical index with {len(documents)} documents")

        except Exception as e:
            logger.error(f"Error building lexical index: {e}", exc_info=True)

    async def search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Perform lexical search using BM25.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of retrieved chunks with scores
        """
        if not self._index_built:
            logger.warning("Lexical index not built, returning empty results")
            return []

        try:
            # Tokenize query
            tokenized_query = self._tokenize(query)

            # Get BM25 scores
            scores = self.index.get_scores(tokenized_query)

            # Get top-k results
            top_indices = scores.argsort()[-top_k:][::-1]

            # Format results
            results = []
            for idx in top_indices:
                doc = self.documents[idx]
                results.append(
                    {
                        "id": doc.get("id"),
                        "text": doc.get("text"),
                        "source": doc.get("source"),
                        "title": doc.get("title"),
                        "page": doc.get("page"),
                        "score": float(scores[idx]),
                        "metadata": doc.get("metadata", {}),
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Error in lexical search: {e}", exc_info=True)
            return []

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return text.split()
