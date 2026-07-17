from __future__ import annotations

import argparse
import asyncio
import json

from pliris.generation.context_assembler import ContextAssembler
from pliris.generation.grounded_generator import (
    GroundedResponseGenerator,
)
from pliris.retrieval.hosted_hybrid import HostedHybridRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run hosted retrieval, assemble grounded context, and generate a validated answer."
        )
    )
    parser.add_argument("question")
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=None)
    return parser


async def async_main() -> int:
    args = build_parser().parse_args()

    retriever = HostedHybridRetriever()
    chunks = await retriever.search(
        args.question,
        top_k=args.top_k,
        document_id=args.document_id,
    )
    context = ContextAssembler(
        max_chunks=args.top_k,
    ).assemble(chunks)
    answer = await GroundedResponseGenerator().generate(
        question=args.question,
        context=context,
        model=args.model,
    )

    print(
        json.dumps(
            {
                "question": args.question,
                "retrieved_count": len(chunks),
                "context": {
                    "source_count": len(context.sources),
                    "character_count": context.character_count,
                    "truncated": context.truncated,
                },
                "result": answer.to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
