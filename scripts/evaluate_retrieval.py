from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any

from evaluation.retrieval_runner import (
    RETRIEVER_CLASSES,
    run_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare hosted Pliris lexical, semantic, and hybrid "
            "retrieval against a strict BABOK benchmark."
        )
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("data/evaluation/retrieval_benchmark.json"),
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        choices=sorted(RETRIEVER_CLASSES),
        default=["lexical", "semantic", "hybrid"],
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmup-count", type=int, default=1)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("artifacts/retrieval_evaluation"),
    )
    return parser


def write_csv(report: dict[str, Any], path: Path) -> None:
    fieldnames = [
        "method",
        "case_id",
        "query",
        "annotation_status",
        "median_latency_ms",
        "p95_latency_ms",
        "returned_count",
        "first_relevant_rank",
        "reciprocal_rank",
        "hit_at_1",
        "hit_at_3",
        "hit_at_5",
        "precision_at_3",
        "evidence_recall_at_5",
        "ranking_stable",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for method, query_reports in report["methods"].items():
            for item in query_reports:
                writer.writerow(
                    {
                        "method": method,
                        **{key: item.get(key) for key in fieldnames if key != "method"},
                    }
                )


def render_markdown(report: dict[str, Any]) -> str:
    benchmark = report["benchmark"]
    lines = [
        f"# {benchmark['name']}",
        "",
        f"- Document: `{benchmark['document_id']}`",
        f"- Cases: {benchmark['case_count']}",
        f"- Top K: {benchmark['top_k']}",
        f"- Repetitions: {benchmark['repetitions']}",
        f"- Warm-up runs per method: {benchmark['warmup_count']}",
        f"- Relevance: `{benchmark['relevance_rule']}`",
        "",
        "## Method summary",
        "",
        (
            "| Method | Queries | MRR | Hit@1 | Hit@3 | "
            "P@3 | Evidence Recall@5 | Median ms | P95 ms |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for item in report["summary"]:
        lines.append(
            "| {method} | {query_count} | "
            "{mean_reciprocal_rank:.3f} | "
            "{hit_rate_at_1:.3f} | {hit_rate_at_3:.3f} | "
            "{mean_precision_at_3:.3f} | "
            "{mean_evidence_recall_at_5:.3f} | "
            "{median_latency_ms:.1f} | "
            "{p95_latency_ms:.1f} |".format(**item)
        )

    lines.extend(["", "## Query results", ""])

    for case_report in report["benchmark_cases"]:
        case_id = case_report["id"]
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"**Query:** {case_report['query']}",
                "",
                (
                    "| Method | First relevant | MRR | P@3 | "
                    "Evidence Recall@5 | Median ms | P95 ms | Stable |"
                ),
                "|---|---:|---:|---:|---:|---:|---:|:---:|",
            ]
        )

        for method, query_reports in report["methods"].items():
            item = next(
                (
                    query_report
                    for query_report in query_reports
                    if query_report["case_id"] == case_id
                ),
                None,
            )
            if item is None:
                continue

            lines.append(
                "| {method} | {first_relevant_rank} | "
                "{reciprocal_rank:.3f} | "
                "{precision_at_3:.3f} | "
                "{evidence_recall_at_5:.3f} | "
                "{median_latency_ms:.1f} | "
                "{p95_latency_ms:.1f} | "
                "{ranking_stable} |".format(
                    method=method,
                    **item,
                )
            )

        lines.append("")

    if report["errors"]:
        lines.extend(["## Errors", ""])
        for error in report["errors"]:
            lines.append("- `{method}` / `{stage}`: {error_type}: {message}".format(**error))
        lines.append("")

    return "\n".join(lines)


async def async_main() -> int:
    args = build_parser().parse_args()

    if args.top_k < 5:
        raise ValueError("--top-k must be at least 5 to calculate Recall@5.")
    if args.repetitions < 1:
        raise ValueError("--repetitions must be at least 1.")
    if args.warmup_count < 0:
        raise ValueError("--warmup-count cannot be negative.")

    report = await run_benchmark(
        args.benchmark,
        methods=args.methods,
        top_k=args.top_k,
        document_id=args.document_id,
        repetitions=args.repetitions,
        warmup_count=args.warmup_count,
    )

    args.output_directory.mkdir(parents=True, exist_ok=True)
    json_path = args.output_directory / "retrieval_baseline.json"
    csv_path = args.output_directory / "retrieval_baseline.csv"
    markdown_path = args.output_directory / "retrieval_baseline.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_csv(report, csv_path)
    markdown_path.write_text(
        render_markdown(report),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": ("completed_with_errors" if report["errors"] else "completed"),
                "benchmark": str(args.benchmark),
                "methods": args.methods,
                "case_count": report["benchmark"]["case_count"],
                "repetitions": args.repetitions,
                "warmup_count": args.warmup_count,
                "json_report": str(json_path),
                "csv_report": str(csv_path),
                "markdown_report": str(markdown_path),
                "summary": report["summary"],
                "error_count": len(report["errors"]),
            },
            indent=2,
        )
    )

    return 1 if report["errors"] else 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
