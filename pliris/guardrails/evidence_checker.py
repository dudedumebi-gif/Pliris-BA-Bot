import logging

from pliris.generation.openai_client import OpenAIClient
from pliris.generation.prompts import EVIDENCE_CHECK_PROMPT

logger = logging.getLogger(__name__)


class EvidenceChecker:
    """Check if responses are supported by evidence in context."""

    def __init__(self):
        self.llm_client = OpenAIClient()

    async def check(self, response: str, context: list[dict]) -> float:
        """
        Check evidence quality for a response.

        Args:
            response: Generated response
            context: Retrieved context chunks

        Returns:
            Evidence score between 0.0 and 1.0
        """
        try:
            # Format context
            context_text = self._format_context(context)

            # Create prompt
            prompt = EVIDENCE_CHECK_PROMPT.format(response=response, context=context_text)

            # Get evidence score
            score_text = await self.llm_client.generate(
                prompt=prompt, model="gpt-4o-mini", max_tokens=20, temperature=0.0
            )

            # Extract numeric score
            score = self._extract_score(score_text)

            logger.info(f"Evidence score: {score}")
            return score

        except Exception as e:
            logger.error(f"Error checking evidence: {e}", exc_info=True)
            return 0.5  # Default to medium confidence on error

    def _format_context(self, context: list[dict]) -> str:
        """Format context for the prompt."""
        if not context:
            return "No context available."

        formatted = []
        for i, chunk in enumerate(context, 1):
            formatted.append(f"Document {i}: {chunk.get('text', '')}")

        return "\n\n".join(formatted)

    def _extract_score(self, text: str) -> float:
        """Extract numeric score from text."""
        try:
            # Look for a number between 0 and 1
            import re

            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0)
        except:
            pass

        return 0.5
