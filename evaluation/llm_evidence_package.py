from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class EvidencePackageError(RuntimeError):
    """Raised when the Phase 6 evidence package cannot be created or verified."""


ARTIFACT_ROOT = Path("artifacts/llm_evaluation/v1/gpt-5-mini")
PACKAGE_RELATIVE_ROOT = ARTIFACT_ROOT / "phase6_evidence"

CONTRACT_PATHS = (
    Path("data/evaluation/llm_evaluation_config.json"),
    Path("data/evaluation/llm_generation_benchmark.json"),
    Path("data/evaluation/llm_prompt_variants.json"),
    Path("data/evaluation/llm_finalist_confirmation.json"),
)

REPRODUCIBILITY_PATHS = (
    Path("README_PHASE_6_STEP_1.md"),
    Path("README_PHASE_6_STEP_2.md"),
    Path("README_PHASE_6_STEP_3.md"),
    Path("README_PHASE_6_STEP_4A.md"),
    Path("README_PHASE_6_STEP_4B.md"),
    Path("evaluation/llm_contract.py"),
    Path("evaluation/llm_contexts.py"),
    Path("evaluation/llm_variant_generator.py"),
    Path("evaluation/llm_scoring.py"),
    Path("evaluation/llm_runner.py"),
    Path("evaluation/llm_human_review.py"),
    Path("evaluation/llm_finalist_contract.py"),
    Path("evaluation/llm_finalist_runner.py"),
    Path("evaluation/llm_finalist_human_review.py"),
    Path("scripts/evaluate_llm_prompts.py"),
    Path("scripts/review_llm_prompts.py"),
    Path("scripts/confirm_llm_finalists.py"),
    Path("scripts/review_llm_finalists.py"),
)

GENERATED_EVIDENCE_PATHS = (
    Path("frozen_contexts.jsonl"),
    Path("primary/automated_scores.csv"),
    Path("primary/raw_outputs.jsonl"),
    Path("primary/summary.json"),
    Path("primary/summary.md"),
    Path("human_review/blinded_responses.csv"),
    Path("human_review/blinding_key.json"),
    Path("human_review/review_instructions.md"),
    Path("human_review/review_manifest.json"),
    Path("human_review/scores.csv"),
    Path("human_review/summary.json"),
    Path("human_review/summary.md"),
    Path("finalist_confirmation/automated_scores.csv"),
    Path("finalist_confirmation/raw_outputs.jsonl"),
    Path("finalist_confirmation/summary.json"),
    Path("finalist_confirmation/summary.md"),
    Path("finalist_confirmation/human_review/blinded_responses.csv"),
    Path("finalist_confirmation/human_review/blinding_key.json"),
    Path("finalist_confirmation/human_review/decision_record.json"),
    Path("finalist_confirmation/human_review/decision_record.md"),
    Path("finalist_confirmation/human_review/review_instructions.md"),
    Path("finalist_confirmation/human_review/review_manifest.json"),
    Path("finalist_confirmation/human_review/scores.csv"),
    Path("finalist_confirmation/human_review/summary.json"),
    Path("finalist_confirmation/human_review/summary.md"),
)

REPORTED_VERIFICATION = {
    "phase_6_step_1": {
        "focused_passed": 10,
        "non_integration_passed": 143,
        "integration_passed": 13,
    },
    "phase_6_step_2": {
        "focused_passed": 18,
        "non_integration_passed": 161,
        "integration_passed": 13,
    },
    "phase_6_step_3": {
        "focused_passed": 19,
        "non_integration_passed": 180,
        "integration_passed": 13,
    },
    "phase_6_step_4a": {
        "focused_passed": 16,
        "non_integration_passed": 196,
        "integration_passed": 13,
    },
    "phase_6_step_4b": {
        "focused_passed": 10,
        "non_integration_passed": 206,
        "integration_passed": 13,
    },
    "known_supabase_deprecation_warnings": 4,
}


@dataclass(frozen=True, slots=True)
class PreparedEvidencePackage:
    root: Path
    package_fingerprint: str
    source_commit: str
    file_count: int
    decision_status: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except FileNotFoundError as exc:
        raise EvidencePackageError(f"Required file not found: {path}") from exc
    return digest.hexdigest()


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidencePackageError(f"Required JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidencePackageError(f"Invalid JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise EvidencePackageError(f"Expected a JSON object: {path}")
    return payload


def _count_jsonl(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(bool(line.strip()) for line in handle)
    except FileNotFoundError as exc:
        raise EvidencePackageError(f"Required JSONL file not found: {path}") from exc


def _count_csv_rows(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return sum(1 for _ in csv.DictReader(handle))
    except FileNotFoundError as exc:
        raise EvidencePackageError(f"Required CSV file not found: {path}") from exc


def _count_jsonl_errors(path: Path) -> int:
    errors = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if record.get("status") == "error":
                    errors += 1
    except FileNotFoundError as exc:
        raise EvidencePackageError(f"Required JSONL file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidencePackageError(f"Invalid JSONL file: {path}") from exc
    return errors


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise EvidencePackageError(f"Git command failed: git {' '.join(args)}") from exc
    return completed.stdout.strip()


def _validate_required_files(repo_root: Path) -> None:
    required = [*CONTRACT_PATHS, *REPRODUCIBILITY_PATHS]
    required.extend(ARTIFACT_ROOT / path for path in GENERATED_EVIDENCE_PATHS)
    missing = [str(path) for path in required if not (repo_root / path).is_file()]
    if missing:
        raise EvidencePackageError(
            "Phase 6 evidence is incomplete; missing files: " + ", ".join(missing)
        )


def _validate_evidence(repo_root: Path) -> dict[str, Any]:
    artifact_root = repo_root / ARTIFACT_ROOT
    primary_raw = artifact_root / "primary/raw_outputs.jsonl"
    finalist_raw = artifact_root / "finalist_confirmation/raw_outputs.jsonl"
    primary_summary = _load_json(artifact_root / "primary/summary.json")
    primary_human = _load_json(artifact_root / "human_review/summary.json")
    finalist_summary = _load_json(artifact_root / "finalist_confirmation/summary.json")
    finalist_human = _load_json(artifact_root / "finalist_confirmation/human_review/summary.json")
    decision = _load_json(artifact_root / "finalist_confirmation/human_review/decision_record.json")

    counts = {
        "frozen_contexts": _count_jsonl(artifact_root / "frozen_contexts.jsonl"),
        "primary_raw_outputs": _count_jsonl(primary_raw),
        "primary_automated_scores": _count_csv_rows(artifact_root / "primary/automated_scores.csv"),
        "primary_human_scores": _count_csv_rows(artifact_root / "human_review/scores.csv"),
        "finalist_raw_outputs": _count_jsonl(finalist_raw),
        "finalist_automated_scores": _count_csv_rows(
            artifact_root / "finalist_confirmation/automated_scores.csv"
        ),
        "finalist_human_scores": _count_csv_rows(
            artifact_root / "finalist_confirmation/human_review/scores.csv"
        ),
        "primary_contract_failures": _count_jsonl_errors(primary_raw),
        "finalist_contract_failures": _count_jsonl_errors(finalist_raw),
    }
    expected_counts = {
        "frozen_contexts": 12,
        "primary_raw_outputs": 36,
        "primary_automated_scores": 36,
        "primary_human_scores": 36,
        "finalist_raw_outputs": 24,
        "finalist_automated_scores": 24,
        "finalist_human_scores": 24,
        "primary_contract_failures": 6,
        "finalist_contract_failures": 3,
    }
    if counts != expected_counts:
        raise EvidencePackageError(
            f"Phase 6 record counts do not match the frozen evidence: {counts}"
        )

    if not primary_summary.get("complete"):
        raise EvidencePackageError("Primary comparison summary is not complete.")
    if primary_summary.get("recorded_attempts") != 36:
        raise EvidencePackageError("Primary comparison does not contain 36 attempts.")
    if primary_human.get("attempts_reviewed") != 36:
        raise EvidencePackageError("Primary human review does not contain 36 attempts.")
    if not finalist_summary.get("complete"):
        raise EvidencePackageError("Finalist confirmation summary is not complete.")
    if finalist_summary.get("recorded_attempts") != 24:
        raise EvidencePackageError("Finalist confirmation does not contain 24 attempts.")
    if finalist_human.get("attempts_reviewed") != 24:
        raise EvidencePackageError("Finalist human review does not contain 24 attempts.")
    if finalist_human.get("selection_status") != "diagnostic_review_complete":
        raise EvidencePackageError("Finalist human review is not finalized.")

    variants = finalist_human.get("variants")
    if not isinstance(variants, list) or len(variants) != 2:
        raise EvidencePackageError("Finalist human summary must contain two variants.")
    if any(bool(item.get("combined_gate_met")) for item in variants):
        raise EvidencePackageError("A finalist unexpectedly passed the combined gate.")

    expected_decision = {
        "decision_status": "no_finalist_selected",
        "selected_variant_id": None,
        "retained_production_prompt": "production_baseline_v1",
        "production_prompt_changed": False,
        "human_review_cannot_override_automated_gate": True,
    }
    for key, expected in expected_decision.items():
        if decision.get(key) != expected:
            raise EvidencePackageError(
                f"Decision record field {key!r} does not match the frozen outcome."
            )

    budget = finalist_summary.get("budget", {})
    if budget.get("generation_api_calls") != 55:
        raise EvidencePackageError("Finalist summary must record 55 total generation calls.")
    if budget.get("estimated_cost_usd") != 0.17483089:
        raise EvidencePackageError("Finalist summary cost does not match the frozen record.")

    return {
        "counts": counts,
        "parent_contract_fingerprint": primary_summary.get("contract_fingerprint"),
        "finalist_contract_fingerprint": finalist_summary.get("finalist_contract_fingerprint"),
        "primary_review_set_fingerprint": primary_human.get("review_set_fingerprint"),
        "finalist_review_set_fingerprint": finalist_human.get("review_set_fingerprint"),
        "total_generation_api_calls": budget.get("generation_api_calls"),
        "estimated_total_cost_usd": budget.get("estimated_cost_usd"),
        "decision": expected_decision,
        "finalist_variants": variants,
    }


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _commands_markdown() -> str:
    return """# Phase 6 Reproducibility Commands

All commands run from the repository root.

## Inspect the frozen primary plan

```bash
uv run python -m scripts.evaluate_llm_prompts --plan
```

## Prepare contexts

```bash
uv run python -m scripts.evaluate_llm_prompts \\
  --prepare-contexts \\
  --embedding-input-price-per-million <CURRENT_RATE>
```

## Run the primary comparison

```bash
uv run python -m scripts.evaluate_llm_prompts \\
  --execute \\
  --generation-input-price-per-million <CURRENT_INPUT_RATE> \\
  --generation-output-price-per-million <CURRENT_OUTPUT_RATE>
```

## Prepare and finalize the primary blinded review

```bash
uv run python -m scripts.review_llm_prompts --prepare
uv run python -m scripts.review_llm_prompts \\
  --finalize \\
  --reviewer-id "Dums"
```

## Inspect and run the finalist confirmation

```bash
uv run python -m scripts.confirm_llm_finalists --plan
uv run python -m scripts.confirm_llm_finalists \\
  --execute \\
  --generation-input-price-per-million <CURRENT_INPUT_RATE> \\
  --generation-output-price-per-million <CURRENT_OUTPUT_RATE>
```

## Prepare and finalize the finalist diagnostic review

```bash
uv run python -m scripts.review_llm_finalists --prepare
uv run python -m scripts.review_llm_finalists \\
  --finalize \\
  --reviewer-id "Dums"
```

The recorded first-run outputs must not be regenerated or replaced. Runtime pricing
placeholders intentionally require current official rates for any future reproduction.
"""


def _readme_markdown(metadata: dict[str, Any]) -> str:
    return f"""# Pliris Phase 6 LLM Evaluation Evidence

This directory is the deliberate, self-contained evidence set for Phase 6.

## Final decision

- Decision: `no_finalist_selected`
- Retained production prompt: `production_baseline_v1`
- Production prompt changed: `False`
- Human review may override a failed automated gate: `False`

The retained baseline is a no-change safety decision. It did not pass the frozen
combined acceptance policy.

## Frozen evidence totals

- Frozen contexts: `{metadata["counts"]["frozen_contexts"]}`
- Primary attempts: `{metadata["counts"]["primary_raw_outputs"]}`
- Primary contract failures: `{metadata["counts"]["primary_contract_failures"]}`
- Finalist attempts: `{metadata["counts"]["finalist_raw_outputs"]}`
- Finalist contract failures: `{metadata["counts"]["finalist_contract_failures"]}`
- Total generation API calls: `{metadata["total_generation_api_calls"]}`
- Estimated total evaluation cost: `${metadata["estimated_total_cost_usd"]:.8f}`

## Contents

- `contracts/` — copied frozen JSON contracts.
- `reproducibility/` — copied tracked workflow code and phase instructions.
- `generated/` — copied source-of-truth first-run outputs and review evidence.
- `commands.md` — documented reproduction sequence.
- `verification.json` — reported local quality gates plus derived evidence checks.
- `manifest.json` — file inventory, hashes, fingerprints, source commit, and decision.
- `checksums.sha256` — package integrity hashes.

Package fingerprint:

`{metadata["package_fingerprint"]}`
"""


def _inventory_files(package_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(package_root.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "checksums.sha256"}:
            continue
        entries.append(
            {
                "path": path.relative_to(package_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return entries


def prepare_evidence_package(
    repo_root: Path,
    *,
    overwrite: bool = False,
) -> PreparedEvidencePackage:
    root = repo_root.resolve()
    _validate_required_files(root)
    evidence = _validate_evidence(root)

    status = _run_git(root, "status", "--short")
    if status:
        raise EvidencePackageError("Working tree must be clean before packaging Phase 6 evidence.")
    source_commit = _run_git(root, "rev-parse", "HEAD")
    source_branch = _run_git(root, "branch", "--show-current")

    package_root = root / PACKAGE_RELATIVE_ROOT
    if package_root.exists():
        if not overwrite:
            raise EvidencePackageError(
                "Phase 6 evidence package already exists. Use --overwrite explicitly."
            )
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)

    for relative in CONTRACT_PATHS:
        _copy_file(root / relative, package_root / "contracts" / relative.name)
    for relative in REPRODUCIBILITY_PATHS:
        _copy_file(root / relative, package_root / "reproducibility" / relative)
    for relative in GENERATED_EVIDENCE_PATHS:
        _copy_file(
            root / ARTIFACT_ROOT / relative,
            package_root / "generated" / relative,
        )

    (package_root / "commands.md").write_text(
        _commands_markdown(),
        encoding="utf-8",
    )
    verification = {
        "reported_local_quality_gates": REPORTED_VERIFICATION,
        "derived_evidence_checks": evidence,
        "external_calls_during_packaging": 0,
        "generation_rerun_performed": False,
        "production_prompt_changed": False,
    }
    (package_root / "verification.json").write_text(
        json.dumps(verification, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    placeholder = dict(evidence)
    placeholder["package_fingerprint"] = "pending"
    (package_root / "README.md").write_text(
        _readme_markdown(placeholder),
        encoding="utf-8",
    )

    entries = _inventory_files(package_root)
    fingerprint_payload = {
        "version": 1,
        "source_commit": source_commit,
        "source_branch": source_branch,
        "decision": evidence["decision"],
        "files": entries,
    }
    package_fingerprint = _canonical_hash(fingerprint_payload)

    readme_metadata = dict(evidence)
    readme_metadata["package_fingerprint"] = package_fingerprint
    (package_root / "README.md").write_text(
        _readme_markdown(readme_metadata),
        encoding="utf-8",
    )
    entries = _inventory_files(package_root)

    manifest = {
        "version": 1,
        "name": "Pliris Phase 6 LLM Evaluation Evidence",
        "source_commit": source_commit,
        "source_branch": source_branch,
        "package_fingerprint": package_fingerprint,
        "generated_evidence_source_root": ARTIFACT_ROOT.as_posix(),
        "decision": evidence["decision"],
        "fingerprints": {
            "parent_contract": evidence["parent_contract_fingerprint"],
            "finalist_contract": evidence["finalist_contract_fingerprint"],
            "primary_human_review": evidence["primary_review_set_fingerprint"],
            "finalist_human_review": evidence["finalist_review_set_fingerprint"],
        },
        "budget": {
            "generation_api_calls": evidence["total_generation_api_calls"],
            "estimated_cost_usd": evidence["estimated_total_cost_usd"],
        },
        "counts": evidence["counts"],
        "files": entries,
    }
    manifest_path = package_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    checksum_paths = sorted(
        path
        for path in package_root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    checksum_lines = [
        f"{_sha256_file(path)}  {path.relative_to(package_root).as_posix()}"
        for path in checksum_paths
    ]
    (package_root / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )

    return PreparedEvidencePackage(
        root=package_root,
        package_fingerprint=package_fingerprint,
        source_commit=source_commit,
        file_count=len(checksum_paths) + 1,
        decision_status=evidence["decision"]["decision_status"],
    )


def verify_evidence_package(repo_root: Path) -> dict[str, Any]:
    package_root = repo_root.resolve() / PACKAGE_RELATIVE_ROOT
    manifest = _load_json(package_root / "manifest.json")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise EvidencePackageError("Evidence manifest is missing its file inventory.")

    for entry in entries:
        if not isinstance(entry, dict):
            raise EvidencePackageError("Evidence manifest contains an invalid file entry.")
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            raise EvidencePackageError("Evidence manifest contains an invalid path.")
        path = package_root / relative
        if not path.is_file():
            raise EvidencePackageError(f"Packaged file is missing: {relative}")
        if path.stat().st_size != entry.get("size_bytes"):
            raise EvidencePackageError(f"Packaged file size mismatch: {relative}")
        if _sha256_file(path) != entry.get("sha256"):
            raise EvidencePackageError(f"Packaged file hash mismatch: {relative}")

    checksum_path = package_root / "checksums.sha256"
    try:
        checksum_lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise EvidencePackageError("Evidence checksum file is missing.") from exc
    for line in checksum_lines:
        digest, separator, relative = line.partition("  ")
        if not separator or not relative:
            raise EvidencePackageError("Evidence checksum file contains an invalid row.")
        path = package_root / relative
        if not path.is_file() or _sha256_file(path) != digest:
            raise EvidencePackageError(f"Checksum verification failed: {relative}")

    decision = manifest.get("decision", {})
    if decision.get("decision_status") != "no_finalist_selected":
        raise EvidencePackageError("Evidence package decision status is invalid.")
    if decision.get("production_prompt_changed") is not False:
        raise EvidencePackageError("Evidence package reports a production prompt change.")

    return {
        "package_fingerprint": manifest.get("package_fingerprint"),
        "source_commit": manifest.get("source_commit"),
        "verified_manifest_files": len(entries),
        "verified_checksums": len(checksum_lines),
        "decision_status": decision.get("decision_status"),
        "production_prompt_changed": decision.get("production_prompt_changed"),
    }
