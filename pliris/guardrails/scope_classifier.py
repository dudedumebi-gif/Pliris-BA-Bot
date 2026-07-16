import logging

from pliris.generation.openai_client import OpenAIClient
from pliris.generation.prompts import SCOPE_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)


class ScopeClassifier:
    """Classify queries to determine if they are within scope."""

    def __init__(self):
        self.llm_client = OpenAIClient()
        self.valid_categories = [
            "business_analysis",
            "business_systems_analysis",
            "project_management",
            "financial",
            "out_of_scope",
        ]

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
                logger.warning("Unexpected scope category returned: %s", category)
                category = "out_of_scope"

            in_scope_categories = {
                "business_analysis",
                "business_systems_analysis",
                "project_management",
                "financial",
            }
            in_scope = category in in_scope_categories

            logger.info(f"Query classified as: {category}, in_scope: {in_scope}")

            return {"category": category, "in_scope": in_scope}

        except Exception as exc:
            logger.exception("Scope classification failed")
            raise RuntimeError("Unable to classify query scope") from exc
