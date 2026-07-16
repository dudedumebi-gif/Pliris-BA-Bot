from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from ingestion.pipeline import IngestionPipeline
from pliris.database.postgres import close_postgres_pool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest one manifest-controlled PDF into hosted Supabase."
    )
    parser.add_argument(
        "--document-id",
        required=True,
        help="Stable document_id from data/corpus_manifest.yaml.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract, clean, and chunk without uploading, embedding, or writing.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Dry-run-only page limit for a low-cost extraction inspection.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace chunks even when the same checksum is already ready.",
    )
    parser.add_argument("--embedding-batch-size", type=int, default=64)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.max_pages is not None and not args.dry_run:
        parser.error("--max-pages may be used only with --dry-run.")

    try:
        summary = IngestionPipeline().ingest(
            args.document_id,
            dry_run=args.dry_run,
            max_pages=args.max_pages,
            force=args.force,
            embedding_batch_size=args.embedding_batch_size,
        )
        print(json.dumps(asdict(summary), indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        close_postgres_pool()


if __name__ == "__main__":
    sys.exit(main())
