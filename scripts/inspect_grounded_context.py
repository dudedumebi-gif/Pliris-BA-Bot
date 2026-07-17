from __future__ import annotations

import argparse
import asyncio
import json

from pliris.generation.context_assembler import ContextAssembler
from pliris.retrieval.hosted_hybrid import HostedHybridRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect production hosted retrieval and deterministic grounded-context assembly."
        )
    )
    parser.add_argument("query")
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-characters", type=int, default=18_000)
    return parser


async def async_main() -> int:
    args = build_parser().parse_args()

    retriever = HostedHybridRetriever()
    chunks = await retriever.search(
        args.query,
        top_k=args.top_k,
        document_id=args.document_id,
    )
    context = ContextAssembler(
        max_chunks=args.top_k,
        max_characters=args.max_characters,
    ).assemble(chunks)

    print(
        json.dumps(
            {
                "query": args.query,
                "document_id": args.document_id,
                "retrieved_count": len(chunks),
                "chunks": [chunk.to_dict() for chunk in chunks],
                "context": context.to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if chunks else 2


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
