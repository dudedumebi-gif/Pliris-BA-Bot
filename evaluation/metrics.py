"""Evaluation metrics for retrieval and LLM performance."""

import logging

logger = logging.getLogger(__name__)


class RetrievalMetrics:
    """Metrics for retrieval evaluation."""

    @staticmethod
    def precision_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
        """
        Calculate precision at k.

        Args:
            retrieved: List of retrieved document IDs
            expected: List of expected document IDs
            k: Cutoff rank

        Returns:
            Precision score
        """
        retrieved_at_k = retrieved[:k]
        relevant_retrieved = len(set(retrieved_at_k) & set(expected))

        return relevant_retrieved / k if k > 0 else 0.0

    @staticmethod
    def recall_at_k(retrieved: list[str], expected: list[str], k: int) -> float:
        """
        Calculate recall at k.

        Args:
            retrieved: List of retrieved document IDs
            expected: List of expected document IDs
            k: Cutoff rank

        Returns:
            Recall score
        """
        retrieved_at_k = retrieved[:k]
        relevant_retrieved = len(set(retrieved_at_k) & set(expected))

        return relevant_retrieved / len(expected) if expected else 0.0

    @staticmethod
    def mean_reciprocal_rank(retrieved: list[str], expected: list[str]) -> float:
        """
        Calculate mean reciprocal rank.

        Args:
            retrieved: List of retrieved document IDs
            expected: List of expected document IDs

        Returns:
            MRR score
        """
        for i, doc_id in enumerate(retrieved):
            if doc_id in expected:
                return 1.0 / (i + 1)

        return 0.0

    @staticmethod
    def f1_score(precision: float, recall: float) -> float:
        """
        Calculate F1 score.

        Args:
            precision: Precision score
            recall: Recall score

        Returns:
            F1 score
        """
        if precision + recall == 0:
            return 0.0

        return 2 * (precision * recall) / (precision + recall)


class LLMMetrics:
    """Metrics for LLM response evaluation."""

    async def evaluate_response(
        self, response: str, criteria: list[str], expected_topics: list[str], citations: list[dict]
    ) -> dict:
        """
        Evaluate an LLM response.

        Args:
            response: Generated response
            criteria: Evaluation criteria
            expected_topics: Topics that should be covered
            citations: Citations provided

        Returns:
            Evaluation scores
        """
        from pliris.generation.openai_client import OpenAIClient

        client = OpenAIClient()

        # Build evaluation prompt
        prompt = f"""Evaluate the following response based on the given criteria.

Response: {response}

Criteria: {", ".join(criteria)}
Expected topics: {", ".join(expected_topics)}

Provide scores (0.0 to 1.0) for:
1. Accuracy: How accurate is the information?
2. Completeness: Does it cover all expected topics?
3. Clarity: How clear and well-structured is the response?

Format as JSON: {{"accuracy": 0.0, "completeness": 0.0, "clarity": 0.0}}"""

        try:
            evaluation_text = await client.generate(
                prompt=prompt, model="gpt-4o-mini", max_tokens=200, temperature=0.0
            )

            # Parse JSON response
            import json

            scores = json.loads(evaluation_text)

            return {
                "accuracy": scores.get("accuracy", 0.0),
                "completeness": scores.get("completeness", 0.0),
                "clarity": scores.get("clarity", 0.0),
                "has_citations": len(citations) > 0,
                "citation_count": len(citations),
            }

        except Exception as e:
            logger.error(f"Error evaluating response: {e}")
            return {
                "accuracy": 0.0,
                "completeness": 0.0,
                "clarity": 0.0,
                "has_citations": len(citations) > 0,
                "citation_count": len(citations),
            }
