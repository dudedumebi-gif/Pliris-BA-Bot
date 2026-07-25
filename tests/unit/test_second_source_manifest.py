from ingestion.manifest_loader import load_manifest


def test_gao_agile_source_is_governed_by_production_manifest() -> None:
    manifest = load_manifest()

    sources = {document.document_id: document for document in manifest.documents}

    source = sources["gao-agile-assessment-guide-2023"]

    assert source.source_filename == "GAO_Agile_Assessment_Guide_2023.pdf"
    assert source.enabled is True
    assert source.include_in_public_repository is False
    assert source.access == "public"
