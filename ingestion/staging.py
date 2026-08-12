from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal, Protocol
from uuid import UUID

from ingestion.models import DocumentManifestEntry

logger = logging.getLogger(__name__)

PROTECTED_STAGING_DOCUMENT_IDS = frozenset({"babok-v3"})


class PdfStagingValidationError(ValueError):
    """Raised when an uploaded PDF fails staging validation."""


class PdfStagingConflictError(RuntimeError):
    """Raised when staging would conflict with an existing document."""


class PdfStagingProtectedSourceError(PermissionError):
    """Raised when staging is attempted for a protected source."""


@dataclass(frozen=True, slots=True)
class ValidatedPdfUpload:
    """Safe metadata derived from a validated PDF upload."""

    safe_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class PdfStagingResult:
    """Result of safely staging a PDF without starting ingestion."""

    database_document_id: UUID
    manifest_id: str
    safe_filename: str
    checksum_sha256: str
    size_bytes: int
    storage_bucket: str
    storage_path: str
    status: Literal["pending"] = "pending"


class PdfStagingRepository(Protocol):
    """Database operations required by PDF staging."""

    def get_document_by_checksum(
        self,
        checksum_sha256: str,
    ) -> dict[str, Any] | None: ...

    def get_document(
        self,
        manifest_id: str,
    ) -> dict[str, Any] | None: ...

    def create_pending_document(
        self,
        *,
        manifest: DocumentManifestEntry,
        checksum_sha256: str,
        size_bytes: int,
        storage_bucket: str,
        storage_path: str,
    ) -> UUID: ...


class PdfStagingStorage(Protocol):
    """Private-storage operations required by PDF staging."""

    bucket: str

    def upload_pdf_bytes(
        self,
        payload: bytes,
        *,
        document_id: str,
        filename: str,
    ) -> str: ...

    def remove(self, storage_path: str) -> None: ...


def validate_pdf_upload(
    *,
    filename: str,
    content_type: str | None,
    payload: bytes,
    max_bytes: int,
) -> ValidatedPdfUpload:
    """Validate a PDF upload without performing external operations."""

    safe_filename = PurePosixPath(filename.replace("\\", "/")).name

    if not safe_filename or not safe_filename.lower().endswith(".pdf"):
        raise PdfStagingValidationError("The upload filename must end with .pdf.")

    normalized_mime_type = (content_type or "").strip().lower()
    if normalized_mime_type != "application/pdf":
        raise PdfStagingValidationError("The upload MIME type must be application/pdf.")

    if not payload:
        raise PdfStagingValidationError("The PDF payload cannot be empty.")

    if max_bytes <= 0:
        raise PdfStagingValidationError("The maximum PDF size must be positive.")

    if len(payload) > max_bytes:
        raise PdfStagingValidationError(f"The PDF size exceeds the {max_bytes}-byte limit.")

    if not payload.startswith(b"%PDF-"):
        raise PdfStagingValidationError("The payload does not contain a valid PDF signature.")

    return ValidatedPdfUpload(
        safe_filename=safe_filename,
        mime_type=normalized_mime_type,
        size_bytes=len(payload),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )


def stage_pdf_upload(
    *,
    manifest: DocumentManifestEntry,
    filename: str,
    content_type: str | None,
    payload: bytes,
    max_bytes: int,
    repository: PdfStagingRepository,
    storage: PdfStagingStorage,
) -> PdfStagingResult:
    """Stage a validated PDF as pending without initiating ingestion."""

    validated = validate_pdf_upload(
        filename=filename,
        content_type=content_type,
        payload=payload,
        max_bytes=max_bytes,
    )

    if manifest.document_id in PROTECTED_STAGING_DOCUMENT_IDS:
        raise PdfStagingProtectedSourceError("This source is protected from PDF staging.")

    manifest_filename = PurePosixPath(manifest.source_filename.replace("\\", "/")).name
    if validated.safe_filename != manifest_filename:
        raise PdfStagingValidationError("The uploaded filename must match the manifest filename.")

    duplicate = repository.get_document_by_checksum(validated.checksum_sha256)
    if duplicate is not None:
        raise PdfStagingConflictError("A source with this PDF checksum is already registered.")

    existing_manifest = repository.get_document(manifest.document_id)
    if existing_manifest is not None:
        raise PdfStagingConflictError("A source with this manifest ID is already registered.")

    storage_path = storage.upload_pdf_bytes(
        payload,
        document_id=manifest.document_id,
        filename=validated.safe_filename,
    )

    try:
        database_document_id = repository.create_pending_document(
            manifest=manifest,
            checksum_sha256=validated.checksum_sha256,
            size_bytes=validated.size_bytes,
            storage_bucket=storage.bucket,
            storage_path=storage_path,
        )
    except Exception:
        try:
            storage.remove(storage_path)
        except Exception:
            logger.exception("Failed to remove staged PDF after persistence failure")
        raise

    return PdfStagingResult(
        database_document_id=database_document_id,
        manifest_id=manifest.document_id,
        safe_filename=validated.safe_filename,
        checksum_sha256=validated.checksum_sha256,
        size_bytes=validated.size_bytes,
        storage_bucket=storage.bucket,
        storage_path=storage_path,
    )
