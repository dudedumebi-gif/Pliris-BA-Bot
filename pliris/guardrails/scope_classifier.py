import logging

from pliris.generation.openai_client import OpenAIClient
from pliris.generation.prompts import SCOPE_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


class ScopeClassifier:
    """Classify queries to determine if they are within scope."""

    def __init__(self):
        self.llm_client = OpenAIClient()
        self.valid_categories = ["business_analysis", "financial", "general", "out_of_scope"]

    async def classify(self, query: str) -> dict:
        """
        Classify a query's scope.

        Args:
            query: User query

        Returns:
            Dictionary with classification results
        """
        try:
            prompt = SCOPE_CLASSIFICATION_PROMPT.format(query=query)

            response = await self.llm_client.generate(
                prompt=prompt, model="gpt-4o-mini", max_tokens=50, temperature=0.0
            )

            # Clean and validate the response
            category = response.strip().lower()

            if category not in self.valid_categories:
                logger.warning(f"Invalid category returned: {category}, defaulting to general")
                category = "general"

            in_scope = category != "out_of_scope"

            logger.info(f"Query classified as: {category}, in_scope: {in_scope}")

            return {"category": category, "in_scope": in_scope}

        except Exception as e:
            logger.error(f"Error classifying query: {e}", exc_info=True)
            # Default to in_scope on error
            return {"category": "general", "in_scope": True}
