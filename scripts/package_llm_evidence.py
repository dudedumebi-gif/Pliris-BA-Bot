from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.llm_evidence_package import (
    EvidencePackageError,
    prepare_evidence_package,
    verify_evidence_package,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or verify the offline Phase 6 LLM evaluation evidence package."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--prepare",
        action="store_true",
        help="Create the deliberate Phase 6 evidence directory.",
    )
    mode.add_argument(
        "--verify",
        action="store_true",
        help="Verify the existing evidence manifest and checksums.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing evidence directory during preparation.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    repo_root = Path.cwd()
    try:
        if args.prepare:
            prepared = prepare_evidence_package(
                repo_root,
                overwrite=args.overwrite,
            )
            print("package_fingerprint:", prepared.package_fingerprint)
            print("source_commit:", prepared.source_commit)
            print("files:", prepared.file_count)
            print("decision_status:", prepared.decision_status)
            print("package_root:", prepared.root)
            print("external_calls: 0")
            return

        verified = verify_evidence_package(repo_root)
        for key, value in verified.items():
            print(f"{key}: {value}")
        print("external_calls: 0")
    except EvidencePackageError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
