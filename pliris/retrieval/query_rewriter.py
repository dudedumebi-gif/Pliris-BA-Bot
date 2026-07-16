import logging

from pliris.generation.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


class QueryRewriter:
    """Rewrite queries for better retrieval performance."""

    def __init__(self):
        self.llm_client = OpenAIClient()

    async def rewrite(self, query: str, conversation_history: list[dict] | None = None) -> str:
        """
        Rewrite a query based on conversation context.

        Args:
            query: Original query
            conversation_history: Previous conversation messages

        Returns:
            Rewritten query optimized for retrieval
        """
        try:
            # If no history, return original query
            if not conversation_history:
                return query

            # Build context from history
            context = self._build_context(conversation_history)

            # Create rewrite prompt
            prompt = f"""
            You are a query rewriting assistant. 
            Rewrite the following user query to make it more specific and better suited for document retrieval.

Conversation context:
{context}

Original query: {query}

Rewritten query (only the query, no explanation):"""

            # Generate rewritten query
            rewritten = await self.llm_client.generate(
                prompt=prompt, model="gpt-4o-mini", max_tokens=100
            )

            # Clean up the response
            rewritten = rewritten.strip()

            # If rewrite is empty or too short, return original
            if len(rewritten) < 5:
                return query

            logger.info(f"Query rewritten: '{query}' -> '{rewritten}'")
            return rewritten

        except Exception as e:
            logger.error(f"Error rewriting query: {e}", exc_info=True)
            return query

    def _build_context(self, history: list[dict]) -> str:
        """Build context string from conversation history."""
        if not history:
            return "No previous conversation."

        context_parts = []
        for msg in history[-5:]:  # Last 5 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context_parts.append(f"{role.upper()}: {content}")

        return "\n".join(context_parts)
