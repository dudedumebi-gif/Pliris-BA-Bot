from pathlib import Path

import pytest

from ingestion.manifest_loader import get_manifest_document, load_manifest


def test_load_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """
version: 1
documents:
  - document_id: sample-ba
    title: Sample BA Document
    source_filename: sample.pdf
    access: private
    include_in_public_repository: false
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)
    assert manifest.version == 1
    assert manifest.documents[0].document_id == "sample-ba"


def test_manifest_rejects_private_public_repository_mix(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        """
version: 1
documents:
  - document_id: invalid
    title: Invalid
    source_filename: invalid.pdf
    access: private
    include_in_public_repository: true
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_manifest(manifest_path)


def test_get_unknown_manifest_document(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("version: 1\ndocuments: []\n", encoding="utf-8")

    with pytest.raises(KeyError):
        get_manifest_document("missing", manifest_path)
