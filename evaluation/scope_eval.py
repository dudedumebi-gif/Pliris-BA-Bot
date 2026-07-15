"""Evaluation script for scope guardrail performance."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from pliris.guardrails.scope_classifier import ScopeClassifier

logger = logging.getLogger(__name__)


class ScopeEvaluator:
    """Evaluate scope guardrail performance."""

    def __init__(self):
        self.classifier = ScopeClassifier()

    async def evaluate_dataset(self, dataset_path: str) -> dict:
        """
        Evaluate scope classification on a dataset.

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
            expected_result = item["expected_result"]
            reason = item.get("reason", "")

            # Classify query
            classification = await self.classifier.classify(query)

            # Determine if classification matches expected
            actual_result = "in_scope" if classification["in_scope"] else "out_of_scope"
            is_correct = actual_result == expected_result

            results.append(
                {
                    "query": query,
                    "expected": expected_result,
                    "actual": actual_result,
                    "correct": is_correct,
                    "reason": reason,
                    "category": classification["category"],
                }
            )

        # Calculate metrics
        correct_count = sum(1 for r in results if r["correct"])
        accuracy = correct_count / len(results) if results else 0.0

        # Calculate per-class metrics
        in_scope_results = [r for r in results if r["expected"] == "in_scope"]
        out_of_scope_results = [r for r in results if r["expected"] == "out_of_scope"]

        in_scope_accuracy = (
            sum(1 for r in in_scope_results if r["correct"]) / len(in_scope_results)
            if in_scope_results
            else 0.0
        )
        out_of_scope_accuracy = (
            sum(1 for r in out_of_scope_results if r["correct"]) / len(out_of_scope_results)
            if out_of_scope_results
            else 0.0
        )

        return {
            "total_queries": len(results),
            "correct_queries": correct_count,
            "accuracy": accuracy,
            "in_scope_accuracy": in_scope_accuracy,
            "out_of_scope_accuracy": out_of_scope_accuracy,
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
    """Run scope evaluation."""
    logging.basicConfig(level=logging.INFO)

    evaluator = ScopeEvaluator()

    # Evaluate scope guardrail
    results = await evaluator.evaluate_dataset(
        "evaluation/datasets/scope_guardrail_questions.jsonl"
    )

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"evaluation/reports/scope_eval_{timestamp}.json"
    evaluator.save_report(results, report_path)

    # Print summary
    print("\n=== Scope Guardrail Evaluation Summary ===")
    print(f"Total Queries: {results['total_queries']}")
    print(f"Correct Classifications: {results['correct_queries']}")
    print(f"Overall Accuracy: {results['accuracy']:.3f}")
    print(f"In-Scope Accuracy: {results['in_scope_accuracy']:.3f}")
    print(f"Out-of-Scope Accuracy: {results['out_of_scope_accuracy']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
