import logging

logger = logging.getLogger(__name__)


class ResponseBuilder:
    """Build structured responses with citations and metadata."""

    def build_response(
        self,
        content: str,
        citations: list[dict] | None = None,
        confidence: float | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Build a structured response.

        Args:
            content: Main response content
            citations: List of citations
            confidence: Confidence score
            metadata: Additional metadata

        Returns:
            Structured response dictionary
        """
        response = {"content": content, "citations": citations or [], "metadata": metadata or {}}

        if confidence is not None:
            response["confidence"] = confidence

        return response

    def format_with_citations(self, content: str, citations: list[dict]) -> str:
        """
        Format content with inline citations.

        Args:
            content: Response content
            citations: List of citations

        Returns:
            Formatted content with citations
        """
        # This is a simplified implementation
        # In production, you'd use more sophisticated citation insertion
        if not citations:
            return content

        formatted = content
        for i, citation in enumerate(citations, 1):
            formatted += f"\n\n[{i}] {citation.get('title', 'Unknown')} - {citation.get('source', 'Unknown')}"

        return formatted

    def add_disclaimer(self, content: str, confidence: float) -> str:
        """
        Add disclaimer based on confidence level.

        Args:
            content: Response content
            confidence: Confidence score

        Returns:
            Content with disclaimer if needed
        """
        if confidence < 0.5:
            disclaimer = "\n\n⚠️ Note: This response is based on limited information. Please verify with additional sources."
            return content + disclaimer

        return content
