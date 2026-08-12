from __future__ import annotations

import hashlib

import pytest

from ingestion.staging import PdfStagingValidationError, validate_pdf_upload


def test_validate_pdf_upload_returns_safe_metadata() -> None:
    payload = b"%PDF-1.7\nvalidated-pdf-content"

    result = validate_pdf_upload(
        filename="../incoming/gao-guide.pdf",
        content_type="application/pdf",
        payload=payload,
        max_bytes=1024,
    )

    assert result.safe_filename == "gao-guide.pdf"
    assert result.mime_type == "application/pdf"
    assert result.size_bytes == len(payload)
    assert result.checksum_sha256 == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize(
    "filename",
    [
        "guide.txt",
        "guide.pdf.exe",
        "guide",
    ],
)
def test_validate_pdf_upload_rejects_non_pdf_filename(filename: str) -> None:
    with pytest.raises(PdfStagingValidationError, match="filename"):
        validate_pdf_upload(
            filename=filename,
            content_type="application/pdf",
            payload=b"%PDF-1.7\ncontent",
            max_bytes=1024,
        )


@pytest.mark.parametrize("content_type", [None, "", "text/plain", "application/octet-stream"])
def test_validate_pdf_upload_rejects_invalid_mime_type(
    content_type: str | None,
) -> None:
    with pytest.raises(PdfStagingValidationError, match="MIME"):
        validate_pdf_upload(
            filename="guide.pdf",
            content_type=content_type,
            payload=b"%PDF-1.7\ncontent",
            max_bytes=1024,
        )


def test_validate_pdf_upload_rejects_empty_payload() -> None:
    with pytest.raises(PdfStagingValidationError, match="empty"):
        validate_pdf_upload(
            filename="guide.pdf",
            content_type="application/pdf",
            payload=b"",
            max_bytes=1024,
        )


def test_validate_pdf_upload_rejects_missing_pdf_signature() -> None:
    with pytest.raises(PdfStagingValidationError, match="signature"):
        validate_pdf_upload(
            filename="guide.pdf",
            content_type="application/pdf",
            payload=b"not-a-pdf",
            max_bytes=1024,
        )


def test_validate_pdf_upload_rejects_oversized_payload() -> None:
    with pytest.raises(PdfStagingValidationError, match="size"):
        validate_pdf_upload(
            filename="guide.pdf",
            content_type="application/pdf",
            payload=b"%PDF-1.7\ncontent",
            max_bytes=8,
        )
