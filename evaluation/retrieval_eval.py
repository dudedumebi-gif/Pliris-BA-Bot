"""Evaluation script for retrieval performance."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from evaluation.metrics import RetrievalMetrics
from pliris.retrieval.hybrid_search import HybridSearch

logger = logging.getLogger(__name__)


class RetrievalEvaluator:
    """Evaluate retrieval system performance."""

    def __init__(self):
        self.search = HybridSearch()
        self.metrics = RetrievalMetrics()

    async def evaluate_dataset(self, dataset_path: str, top_k: int = 10) -> dict:
        """
        Evaluate retrieval on a dataset.

        Args:
            dataset_path: Path to JSONL dataset
            top_k: Number of results to retrieve

        Returns:
            Evaluation results
        """
        # Load dataset
        questions = self._load_dataset(dataset_path)

        results = []

        for item in questions:
            query = item["query"]
            expected_docs = item.get("expected_documents", [])

            # Retrieve results
            retrieved = await self.search.search(query, top_k=top_k)
            retrieved_docs = [r.get("source") for r in retrieved]

            # Calculate metrics
            precision = self.metrics.precision_at_k(retrieved_docs, expected_docs, top_k)
            recall = self.metrics.recall_at_k(retrieved_docs, expected_docs, top_k)
            mrr = self.metrics.mean_reciprocal_rank(retrieved_docs, expected_docs)

            results.append(
                {
                    "query": query,
                    "expected": expected_docs,
                    "retrieved": retrieved_docs,
                    "precision": precision,
                    "recall": recall,
                    "mrr": mrr,
                }
            )

        # Aggregate metrics
        avg_precision = sum(r["precision"] for r in results) / len(results)
        avg_recall = sum(r["recall"] for r in results) / len(results)
        avg_mrr = sum(r["mrr"] for r in results) / len(results)

        return {
            "total_queries": len(results),
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_mrr": avg_mrr,
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
    """Run retrieval evaluation."""
    logging.basicConfig(level=logging.INFO)

    evaluator = RetrievalEvaluator()

    # Evaluate retrieval
    results = await evaluator.evaluate_dataset("evaluation/datasets/retrieval_questions.jsonl")

    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"evaluation/reports/retrieval_eval_{timestamp}.json"
    evaluator.save_report(results, report_path)

    # Print summary
    print("\n=== Retrieval Evaluation Summary ===")
    print(f"Total Queries: {results['total_queries']}")
    print(f"Average Precision@10: {results['avg_precision']:.3f}")
    print(f"Average Recall@10: {results['avg_recall']:.3f}")
    print(f"Average MRR: {results['avg_mrr']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
