from __future__ import annotations

import ast
from pathlib import Path

SOURCE_PAGE = Path("app/developer_pages/2_Sources.py")


def test_source_page_exposes_only_guarded_source_mutations() -> None:
    source = SOURCE_PAGE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    client_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "client"
    }

    assert client_calls == {
        "archive_source",
        "get_chunks",
        "get_events",
        "get_source",
        "get_stats",
        "list_sources",
        "restore_source",
        "stage_pdf",
    }
    # Controlled staging permits exactly one guarded PDF uploader.
    assert source.count("st.file_uploader(") == 1
    assert source.count("client.stage_pdf(") == 1
    assert "STAGING_ACCEPTANCE_MANIFEST_ID" in source
    assert "staging_filename_for_manifest" in source
    assert "accept_multiple_files=False" in source
    assert "No ingestion was started." in source
    assert "delete_source" not in source
    assert "reingest_source" not in source
    assert "max_upload_size=settings.pdf_staging_max_mib" in source


def test_source_page_enforces_lifecycle_safety_contract() -> None:
    source = SOURCE_PAGE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    rendered_text = "\n".join(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )

    required_identifiers = {
        "PROTECTED_LIFECYCLE_MANIFEST_IDS",
        "lifecycle_action_for_source",
        "validate_lifecycle_input",
    }
    required_copy = {
        "append-only audit history",
        "Indexed chunks remain retained",
        "every retained chunk still has an embedding",
        "Details, metrics, and audit history were refreshed",
    }

    missing_identifiers = {name for name in required_identifiers if name not in source}
    missing_copy = {fragment for fragment in required_copy if fragment not in rendered_text}
    assert not missing_identifiers
    assert not missing_copy
