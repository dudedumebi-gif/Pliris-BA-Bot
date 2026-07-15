import logging
import re

logger = logging.getLogger(__name__)


class CitationFormatter:
    """Format and extract citations from responses."""

    def extract_citations(self, response: str, context: list[dict]) -> list[dict]:
        """
        Extract citations from response based on context.

        Args:
            response: Generated response
            context: Retrieved context chunks

        Returns:
            List of formatted citations
        """
        citations = []

        # Look for citation patterns like [Document 1], [1], etc.
        citation_pattern = r"\[Document (\d+)\]|\[(\d+)\]"
        matches = re.findall(citation_pattern, response)

        for match in matches:
            doc_num = int(match[0] if match[0] else match[1])

            # Get the corresponding context document
            if 0 < doc_num <= len(context):
                source_doc = context[doc_num - 1]
                citations.append(
                    {
                        "source": source_doc.get("source", "Unknown"),
                        "title": source_doc.get("title", "Unknown"),
                        "text": source_doc.get("text", "")[:200],
                        "page": source_doc.get("page"),
                        "score": source_doc.get("score", 0.0),
                        "metadata": source_doc.get("metadata", {}),
                    }
                )

        return citations

    def format_citation(self, citation: dict, index: int) -> str:
        """
        Format a single citation.

        Args:
            citation: Citation data
            index: Citation number

        Returns:
            Formatted citation string
        """
        return f"[{index}] {citation.get('title', 'Unknown')} ({citation.get('source', 'Unknown')})"

    def build_bibliography(self, citations: list[dict]) -> str:
        """
        Build a bibliography from citations.

        Args:
            citations: List of citations

        Returns:
            Formatted bibliography
        """
        if not citations:
            return ""

        bibliography = "\n\n## References\n"
        for i, citation in enumerate(citations, 1):
            bibliography += f"{i}. {citation.get('title', 'Unknown')}. "
            bibliography += f"Source: {citation.get('source', 'Unknown')}"
            if citation.get("page"):
                bibliography += f", Page {citation['page']}"
            bibliography += "\n"

        return bibliography
