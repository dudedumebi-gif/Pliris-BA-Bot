from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.llm_contract import load_evaluation_contract
from evaluation.llm_finalist_contract import (
    finalist_output_root,
    load_finalist_confirmation_contract,
)
from evaluation.llm_finalist_human_review import (
    FinalistHumanReviewError,
    finalist_review_paths,
    finalize_finalist_review,
    prepare_finalist_review,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or finalize Step 4B finalist review.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--finalize", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--reviewer-id")
    return parser


def main() -> None:
    args = _parser().parse_args()
    root = Path.cwd()
    try:
        if args.prepare:
            key = prepare_finalist_review(root, overwrite=args.overwrite)
            parent = load_evaluation_contract(root)
            confirmation = load_finalist_confirmation_contract(root, parent)
            paths = finalist_review_paths(finalist_output_root(root, confirmation))
            failed = sum(item.response_status == "contract_failure" for item in key.assignments)
            print("review_set_fingerprint:", key.review_set_fingerprint)
            print("attempts:", key.attempt_count)
            print("accepted_responses:", key.attempt_count - failed)
            print("contract_failures:", failed)
            print("blinded_responses:", paths.review_csv.resolve())
            print("scores:", paths.scores_csv.resolve())
            print("instructions:", paths.instructions_md.resolve())
            print("external_calls: 0")
            return
        if not args.reviewer_id:
            raise FinalistHumanReviewError("--reviewer-id is required with --finalize.")
        result = finalize_finalist_review(root, reviewer_id=args.reviewer_id)
        print("attempts_reviewed:", result["summary"]["attempts_reviewed"])
        print("decision_status:", result["decision"]["decision_status"])
        print("selected_variant_id:", result["decision"]["selected_variant_id"])
        print("production_prompt_changed:", result["decision"]["production_prompt_changed"])
        print("summary:", result["paths"].summary_md.resolve())
        print("decision_record:", result["paths"].decision_md.resolve())
        print("external_calls: 0")
    except FinalistHumanReviewError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
