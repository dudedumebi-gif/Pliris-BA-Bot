from __future__ import annotations

import argparse
import json
import sys

from ingestion.embedding_service import EmbeddingService
from pliris.config.settings import get_settings
from pliris.database.supabase_client import get_supabase_admin_client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a hybrid-search smoke test against hosted Supabase."
    )
    parser.add_argument("query")
    parser.add_argument("--match-count", type=int, default=5)
    parser.add_argument(
        "--document-id",
        default=None,
        help="Optional manifest document ID filter.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    client = get_supabase_admin_client()

    filter_ids = None
    if args.document_id:
        response = (
            client.table("documents")
            .select("id")
            .eq("manifest_id", args.document_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            print(f"Document not found: {args.document_id}", file=sys.stderr)
            return 1
        filter_ids = [response.data[0]["id"]]

    embedding = EmbeddingService().embed_texts([args.query]).embeddings[0]
    response = client.rpc(
        "hybrid_search",
        {
            "query_text": args.query,
            "query_embedding": embedding,
            "match_count": args.match_count,
            "full_text_weight": settings.full_text_weight,
            "semantic_weight": settings.semantic_weight,
            "rrf_k": settings.rrf_k,
            "filter_document_ids": filter_ids,
        },
    ).execute()

    rows = response.data or []
    output = [
        {
            "rank": index,
            "document_title": row["document_title"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "score": row["score"],
            "snippet": row["content"][:500],
        }
        for index, row in enumerate(rows, start=1)
    ]
    print(json.dumps(output, indent=2))
    return 0 if output else 2


if __name__ == "__main__":
    sys.exit(main())
