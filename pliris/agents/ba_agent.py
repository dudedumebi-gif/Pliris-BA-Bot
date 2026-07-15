import logging

from pliris.generation.citations import CitationFormatter
from pliris.generation.openai_client import OpenAIClient
from pliris.generation.prompts import BUSINESS_ANALYST_PROMPT

logger = logging.getLogger(__name__)


class BAAgent:
    """Business Analyst Agent for processing queries and generating responses."""

    def __init__(self):
        self.llm_client = OpenAIClient()
        self.citation_formatter = CitationFormatter()

    async def process_query(
        self, query: str, context: list[dict], conversation_history: list[dict] | None = None
    ) -> dict:
        """
        Process a query with retrieved context and generate a response.

        Args:
            query: The user's question
            context: Retrieved document chunks
            conversation_history: Previous messages in the conversation

        Returns:
            Dictionary with response and metadata
        """
        try:
            # Format context for the prompt
            context_text = self._format_context(context)

            # Build conversation history
            history_text = self._format_history(conversation_history or [])

            # Create the full prompt
            prompt = BUSINESS_ANALYST_PROMPT.format(
                context=context_text, history=history_text, query=query
            )

            # Generate response
            response = await self.llm_client.generate(prompt=prompt, model="gpt-4o")

            # Extract citations
            citations = self.citation_formatter.extract_citations(response, context)

            return {"response": response, "citations": citations, "context_used": len(context)}

        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            raise

    def _format_context(self, context: list[dict]) -> str:
        """Format retrieved context for the prompt."""
        if not context:
            return "No relevant documents found."

        formatted = []
        for i, chunk in enumerate(context, 1):
            formatted.append(
                f"Document {i} (Source: {chunk.get('source', 'Unknown')}):\n{chunk.get('text', '')}"
            )

        return "\n\n".join(formatted)

    def _format_history(self, history: list[dict]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "No previous conversation."

        formatted = []
        for msg in history[-10:]:  # Last 10 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content}")

        return "\n".join(formatted)
