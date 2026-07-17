from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.layout_audit import audit_pdf_layout
from ingestion.manifest_loader import get_manifest_document, resolve_source_path

DEFAULT_PAGES = [
    12,
    13,
    43,
    44,
    59,
    60,
    89,
    92,
    93,
    354,
    355,
    460,
    461,
]


def parse_pages(value: str) -> list[int]:
    pages = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not pages or any(page < 1 for page in pages):
        raise argparse.ArgumentTypeError(
            "Pages must be a comma-separated list of positive integers."
        )
    return pages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit recurring and positioned PDF text blocks before changing BABOK extraction rules."
        )
    )
    parser.add_argument("--document-id", default="babok-v3")
    parser.add_argument(
        "--pages",
        type=parse_pages,
        default=DEFAULT_PAGES,
        help="Representative pages, separated by commas.",
    )
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--minimum-pages", type=int, default=5)
    parser.add_argument("--minimum-page-ratio", type=float, default=0.02)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("artifacts/layout_audit"),
    )
    return parser


def render_text_report(audit: dict) -> str:
    lines = [
        "Pliris BA Bot - PDF Layout Audit",
        "=" * 36,
        f"PDF: {audit['pdf_path']}",
        f"Total pages: {audit['total_pages']}",
        f"Analyzed pages: {audit['analyzed_pages']}",
        f"Text blocks: {audit['block_count']}",
        f"Repeated candidates: {audit['candidate_count']}",
        "",
        "Top repeated candidates",
        "-" * 24,
    ]

    for candidate in audit["repeated_candidates"][:40]:
        sample = candidate["sample_text"].replace("\n", " ")
        lines.extend(
            [
                f"Text: {sample[:180]}",
                f"Page count: {candidate['page_count']}",
                f"Page ratio: {candidate['page_ratio']}",
                f"Locations: {candidate['locations']}",
                f"Reasons: {candidate['reasons']}",
                f"Sample pages: {candidate['sample_pages']}",
                "",
            ]
        )

    lines.extend(["Representative page blocks", "-" * 26])

    for page_number, blocks in audit["selected_pages"].items():
        lines.append(f"\nPAGE {page_number}")
        lines.append("~" * (5 + len(page_number)))

        for block in blocks:
            sample = block["text"].replace("\n", " ")
            lines.append(
                f"[{block['location']}] "
                f"bbox=({block['x0']:.1f},{block['y0']:.1f},"
                f"{block['x1']:.1f},{block['y1']:.1f}) "
                f"repeat_pages={block['repeat_page_count']} "
                f"reasons={block['candidate_reasons']} "
                f"text={sample[:240]}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = build_parser().parse_args()
    manifest_entry = get_manifest_document(args.document_id)
    source_path = resolve_source_path(manifest_entry)

    audit = audit_pdf_layout(
        source_path,
        selected_pages=args.pages,
        max_pages=args.max_pages,
        minimum_pages=args.minimum_pages,
        minimum_page_ratio=args.minimum_page_ratio,
    )

    args.output_directory.mkdir(parents=True, exist_ok=True)
    json_path = args.output_directory / f"{args.document_id}_layout_audit.json"
    text_path = args.output_directory / f"{args.document_id}_layout_audit.txt"

    json_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    text_path.write_text(
        render_text_report(audit),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "completed",
                "json_report": str(json_path),
                "text_report": str(text_path),
                "total_pages": audit["total_pages"],
                "analyzed_pages": audit["analyzed_pages"],
                "block_count": audit["block_count"],
                "candidate_count": audit["candidate_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
