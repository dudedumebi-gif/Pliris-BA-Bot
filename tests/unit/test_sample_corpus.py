from pathlib import Path

import pymupdf

from ingestion.manifest_loader import load_manifest
from scripts.build_sample_corpus import build_pdf


def test_public_sample_is_declared_and_redistributable() -> None:
    manifest = load_manifest(Path("data/corpus_manifest.yaml"))
    sample = next(
        item for item in manifest.documents if item.document_id == "pliris-public-ba-primer"
    )

    assert sample.access == "public"
    assert sample.include_in_public_repository is True
    assert Path("data/sample", sample.source_filename).is_file()


def test_sample_pdf_can_be_rebuilt_and_extracted(tmp_path: Path) -> None:
    output = tmp_path / "sample.pdf"
    build_pdf(Path("data/sample/public_ba_primer.md"), output)
    first_build = output.read_bytes()
    build_pdf(Path("data/sample/public_ba_primer.md"), output)

    with pymupdf.open(output) as document:
        text = "".join(page.get_text() for page in document)

    assert output.read_bytes() == first_build
    assert "Stakeholder analysis" in text
    assert "Acceptance criteria" in text
