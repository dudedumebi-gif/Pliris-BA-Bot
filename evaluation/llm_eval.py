"""Evaluation script for LLM response quality."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from evaluation.metrics import LLMMetrics
from pliris.agents.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)


class LLMEvaluator:
    """Evaluate LLM response quality."""

    def __init__(self):
        self.orchestrator = AgentOrchestrator()
        self.metrics = LLMMetrics()

    async def evaluate_dataset(self, dataset_path: str) -> dict:
        """
        Evaluate LLM responses on a dataset.

        Args:
            dataset_path: Path to JSONL dataset

        Returns:
            Evaluation results
        """
        # Load dataset
        questions = self._load_dataset(dataset_path)

        results = []

        for item in questions:
            query = item["query"]
            criteria = item.get("criteria", ["accuracy", "completeness", "clarity"])
            expected_topics = item.get("expected_topics", [])

            # Generate response
            try:
                response_data = await self.orchestrator.process_query(
                    message=query, conversation_id=None, user_id="evaluator"
                )

                response = response_data["response"]
                citations = response_data.get("citations", [])
                confidence = response_data.get("confidence", 0.0)

                # Evaluate response
                evaluation = await self.metrics.evaluate_response(
                    response=response,
                    criteria=criteria,
                    expected_topics=expected_topics,
                    citations=citations,
                )

                results.append(
                    {
                        "query": query,
                        "response": response,
                        "confidence": confidence,
                        "citation_count": len(citations),
                        "evaluation": evaluation,
                    }
                )

            except Exception as e:
                logger.error(f"Error evaluating query: {e}")
                results.append({"query": query, "error": str(e)})

        # Aggregate metrics
        successful_results = [r for r in results if "error" not in r]

        if successful_results:
            avg_accuracy = sum(r["evaluation"]["accuracy"] for r in successful_results) / len(
                successful_results
            )
            avg_completeness = sum(
                r["evaluation"]["completeness"] for r in successful_results
            ) / len(successful_results)
            avg_clarity = sum(r["evaluation"]["clarity"] for r in successful_results) / len(
                successful_results
            )
            avg_confidence = sum(r["confidence"] for r in successful_results) / len(
                successful_results
            )
        else:
            avg_accuracy = avg_completeness = avg_clarity = avg_confidence = 0.0

        return {
            "total_queries": len(results),
            "successful_queries": len(successful_results),
            "avg_accuracy": avg_accuracy,
            "avg_completeness": avg_completeness,
            "avg_clarity": avg_clarity,
            "avg_confidence": avg_confidence,
            "results": results,
        }

    def _load_dataset(self, path: str) -> list[dict]:
        """Load evaluation dataset from JSONL file."""
        questions = []
        with open(path) as f:
            for line in f:
                questions.append(json.loads(line))
        return questions

    def save_report(self, results: dict, output_path: str):
        """Save evaluation results to file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Saved evaluation report to {output_path}")


async def main():
    """Run LLM evaluation."""
    logging.basicConfig(level=logging.INFO)

    evaluator = LLMEvaluator()

    # Evaluate LLM
    results = await evaluator.evaluate_dataset("evaluation/datasets/llm_questions.jsonl")

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"evaluation/reports/llm_eval_{timestamp}.json"
    evaluator.save_report(results, report_path)

    # Print summary
    print("\n=== LLM Evaluation Summary ===")
    print(f"Total Queries: {results['total_queries']}")
    print(f"Successful Queries: {results['successful_queries']}")
    print(f"Average Accuracy: {results['avg_accuracy']:.3f}")
    print(f"Average Completeness: {results['avg_completeness']:.3f}")
    print(f"Average Clarity: {results['avg_clarity']:.3f}")
    print(f"Average Confidence: {results['avg_confidence']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
