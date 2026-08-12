from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.llm_human_review import (
    HumanReviewError,
    finalize_human_review,
    prepare_human_review,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Prepare or finalize the offline Phase 6 blinded human review.")
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare",
        action="store_true",
        help="Create the blinded response set and score sheet.",
    )
    mode.add_argument(
        "--finalize",
        action="store_true",
        help="Validate completed scores and generate the unblinded summary.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an unstarted review package.",
    )
    parser.add_argument(
        "--reviewer-id",
        help="Reviewer name or stable alias; required with --finalize.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    repo_root = Path.cwd()

    try:
        if args.prepare:
            prepared = prepare_human_review(repo_root, overwrite=args.overwrite)
            failed = sum(
                row["response_status"] == "contract_failure" for row in prepared.review_rows
            )
            print("review_set_fingerprint:", prepared.key.review_set_fingerprint)
            print("attempts:", prepared.key.attempt_count)
            print("accepted_responses:", len(prepared.review_rows) - failed)
            print("contract_failures:", failed)
            print("blinded_responses:", prepared.paths.review_csv)
            print("scores:", prepared.paths.scores_csv)
            print("instructions:", prepared.paths.instructions_md)
            print("external_calls: 0")
            return

        if not args.reviewer_id:
            raise HumanReviewError("--reviewer-id is required with --finalize.")
        summary = finalize_human_review(
            repo_root,
            reviewer_id=args.reviewer_id,
        )
        print("attempts_reviewed:", summary["attempts_reviewed"])
        print("selection_status:", summary["selection_status"])
        print(
            "summary:",
            (
                repo_root / "artifacts/llm_evaluation/v1/gpt-5-mini/human_review/summary.md"
            ).resolve(),
        )
        print("external_calls: 0")
    except HumanReviewError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
