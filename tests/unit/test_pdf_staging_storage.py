from __future__ import annotations

from unittest.mock import Mock

from ingestion.storage_service import KnowledgeBaseStorage


def test_upload_pdf_bytes_uses_non_overwriting_storage_options() -> None:
    payload = b"%PDF-1.7\nvalidated-pdf-content"
    bucket_client = Mock()
    client = Mock()
    client.storage.from_.return_value = bucket_client

    storage = KnowledgeBaseStorage.__new__(KnowledgeBaseStorage)
    storage.client = client
    storage.bucket = "knowledge-base"

    storage_path = storage.upload_pdf_bytes(
        payload,
        document_id="gao-guide-staging-test",
        filename="gao-guide.pdf",
    )

    assert storage_path == "gao-guide-staging-test/gao-guide.pdf"
    client.storage.from_.assert_called_once_with("knowledge-base")
    bucket_client.upload.assert_called_once_with(
        path="gao-guide-staging-test/gao-guide.pdf",
        file=payload,
        file_options={
            "content-type": "application/pdf",
            "upsert": "false",
        },
    )
