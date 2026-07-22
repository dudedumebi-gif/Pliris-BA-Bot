from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.llm_evidence_package import (
    EvidencePackageError,
    _canonical_hash,
    _count_csv_rows,
    _count_jsonl,
    _load_json,
    _sha256_file,
    verify_evidence_package,
)


def test_canonical_hash_is_order_independent() -> None:
    first = _canonical_hash({"a": 1, "b": 2})
    second = _canonical_hash({"b": 2, "a": 1})
    assert first == second


def test_sha256_file_is_stable(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("pliris\n", encoding="utf-8")
    assert _sha256_file(path) == _sha256_file(path)


def test_missing_hash_source_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(EvidencePackageError, match="Required file not found"):
        _sha256_file(tmp_path / "missing.txt")


def test_load_json_requires_object(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(EvidencePackageError, match="Expected a JSON object"):
        _load_json(path)


def test_count_jsonl_ignores_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
    assert _count_jsonl(path) == 2


def test_count_csv_rows_excludes_header(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text("id,value\n1,a\n2,b\n", encoding="utf-8")
    assert _count_csv_rows(path) == 2


def _write_package(tmp_path: Path) -> Path:
    root = tmp_path / "artifacts/llm_evaluation/v1/gpt-5-mini/phase6_evidence"
    root.mkdir(parents=True)
    payload = root / "README.md"
    payload.write_text("evidence\n", encoding="utf-8")
    digest = _sha256_file(payload)
    manifest = {
        "package_fingerprint": "f" * 64,
        "source_commit": "a" * 40,
        "decision": {
            "decision_status": "no_finalist_selected",
            "production_prompt_changed": False,
        },
        "files": [
            {
                "path": "README.md",
                "size_bytes": payload.stat().st_size,
                "sha256": digest,
            }
        ],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    checksums = [
        f"{digest}  README.md",
        f"{_sha256_file(manifest_path)}  manifest.json",
    ]
    (root / "checksums.sha256").write_text(
        "\n".join(checksums) + "\n",
        encoding="utf-8",
    )
    return root


def test_verify_valid_package(tmp_path: Path) -> None:
    _write_package(tmp_path)
    verified = verify_evidence_package(tmp_path)
    assert verified["decision_status"] == "no_finalist_selected"
    assert verified["production_prompt_changed"] is False


def test_verify_rejects_tampered_file(tmp_path: Path) -> None:
    root = _write_package(tmp_path)
    (root / "README.md").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(EvidencePackageError, match=r"size mismatch|hash mismatch"):
        verify_evidence_package(tmp_path)


def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    root = _write_package(tmp_path)
    (root / "README.md").unlink()
    with pytest.raises(EvidencePackageError, match="Packaged file is missing"):
        verify_evidence_package(tmp_path)


def test_verify_rejects_changed_decision(tmp_path: Path) -> None:
    root = _write_package(tmp_path)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["decision"]["decision_status"] = "finalist_selected"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    checksum_path = root / "checksums.sha256"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    lines[1] = f"{_sha256_file(manifest_path)}  manifest.json"
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(EvidencePackageError, match="decision status"):
        verify_evidence_package(tmp_path)


def test_count_frozen_context_records_excludes_manifest(tmp_path):
    from evaluation.llm_evidence_package import _count_frozen_context_records

    path = tmp_path / "frozen_contexts.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"record_type":"manifest","case_count":2}',
                '{"record_type":"context","case_id":"case-1"}',
                '{"record_type":"context","case_id":"case-2"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert _count_frozen_context_records(path) == 2


def test_count_frozen_context_records_rejects_manifest_mismatch(tmp_path):
    from evaluation.llm_evidence_package import (
        EvidencePackageError,
        _count_frozen_context_records,
    )

    path = tmp_path / "frozen_contexts.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"record_type":"manifest","case_count":2}',
                '{"record_type":"context","case_id":"case-1"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        EvidencePackageError,
        match="manifest case_count does not match",
    ):
        _count_frozen_context_records(path)
