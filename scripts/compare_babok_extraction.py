from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz

from ingestion.layout_filter import (
    blocks_to_text,
    build_layout_filter_policy,
    filter_blocks,
    page_text_blocks,
)
from ingestion.manifest_loader import get_manifest_document, resolve_source_path

DEFAULT_PAGES = [12, 13, 43, 44, 59, 60, 89, 92, 93, 354, 355, 460, 461]


def parse_pages(value: str) -> list[int]:
    pages = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not pages or any(page < 1 for page in pages):
        raise argparse.ArgumentTypeError(
            "Pages must be a comma-separated list of positive integers."
        )
    return pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare raw and conservatively filtered BABOK text blocks."
    )
    parser.add_argument("--document-id", default="babok-v3")
    parser.add_argument("--pages", type=parse_pages, default=DEFAULT_PAGES)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("artifacts/layout_audit"),
    )
    return parser


def render_text_report(report: dict) -> str:
    lines = [
        "Pliris BA Bot - Extraction Comparison",
        "=" * 39,
        f"PDF: {report['pdf_path']}",
        f"Learned repeated patterns: {report['learned_pattern_count']}",
        f"Selected pages: {report['selected_pages']}",
        f"Removed repeated artifacts: {report['removed_repeated_artifacts']}",
        f"Removed printed page numbers: {report['removed_page_numbers']}",
        "",
        "Learned artifact evidence",
        "-" * 25,
    ]

    for evidence in report["policy_evidence"].values():
        lines.extend(
            [
                f"Text: {evidence['sample_text']}",
                f"Page count: {evidence['page_count']}",
                f"Page ratio: {evidence['page_ratio']}",
                f"Edge ratio: {evidence['edge_ratio']}",
                f"Locations: {evidence['locations']}",
                "",
            ]
        )

    for page in report["pages"]:
        lines.extend(
            [
                "",
                f"PAGE {page['page_number']}",
                "~" * (5 + len(str(page["page_number"]))),
                "",
                "REMOVED BLOCKS",
                "-" * 14,
            ]
        )

        if not page["removed"]:
            lines.append("(none)")
        else:
            for removed in page["removed"]:
                lines.append(f"{removed['reason']}: {removed['text'].replace(chr(10), ' ')}")

        lines.extend(
            [
                "",
                "CLEANED TEXT",
                "-" * 12,
                page["cleaned_text"],
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = build_parser().parse_args()
    manifest = get_manifest_document(args.document_id)
    source_path = resolve_source_path(manifest)
    policy = build_layout_filter_policy(source_path)

    page_reports: list[dict] = []
    removed_repeated_artifacts = 0
    removed_page_numbers = 0

    with fitz.open(source_path) as document:
        for page_number in args.pages:
            if page_number > document.page_count:
                raise ValueError(
                    f"Page {page_number} exceeds PDF page count {document.page_count}."
                )

            page = document.load_page(page_number - 1)
            blocks = page_text_blocks(page, page_number=page_number)
            kept, stats, removed = filter_blocks(blocks, policy)

            removed_repeated_artifacts += stats.removed_repeated_artifacts
            removed_page_numbers += stats.removed_page_numbers

            page_reports.append(
                {
                    "page_number": page_number,
                    "removed": removed,
                    "cleaned_text": blocks_to_text(kept),
                }
            )

    report = {
        "pdf_path": str(source_path),
        "selected_pages": args.pages,
        "learned_pattern_count": len(policy.repeated_artifact_texts),
        "policy_evidence": policy.evidence,
        "removed_repeated_artifacts": removed_repeated_artifacts,
        "removed_page_numbers": removed_page_numbers,
        "pages": page_reports,
    }

    args.output_directory.mkdir(parents=True, exist_ok=True)
    json_path = args.output_directory / f"{args.document_id}_extraction_comparison.json"
    text_path = args.output_directory / f"{args.document_id}_extraction_comparison.txt"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    text_path.write_text(
        render_text_report(report),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "completed",
                "json_report": str(json_path),
                "text_report": str(text_path),
                "learned_pattern_count": report["learned_pattern_count"],
                "selected_page_count": len(args.pages),
                "removed_repeated_artifacts": (removed_repeated_artifacts),
                "removed_page_numbers": removed_page_numbers,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
