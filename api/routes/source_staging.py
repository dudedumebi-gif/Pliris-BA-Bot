from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.developer_access import require_developer_access
from api.schemas.sources import SourceStagingResponse
from ingestion.manifest_loader import get_manifest_document
from ingestion.models import DocumentManifestEntry
from ingestion.repository import IngestionRepository
from ingestion.staging import (
    PdfStagingConflictError,
    PdfStagingProtectedSourceError,
    PdfStagingValidationError,
    stage_pdf_upload,
)
from ingestion.storage_service import KnowledgeBaseStorage
from pliris.config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_developer_access)])


def get_pdf_staging_repository() -> IngestionRepository:
    return IngestionRepository()


def get_pdf_staging_storage() -> KnowledgeBaseStorage:
    return KnowledgeBaseStorage()


def get_pdf_staging_max_bytes() -> int:
    return get_settings().pdf_staging_max_bytes


def get_pdf_staging_manifest(
    manifest_id: Annotated[str, Form(min_length=1, max_length=200)],
) -> DocumentManifestEntry:
    try:
        return get_manifest_document(manifest_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manifest source not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Manifest source is not available for staging.",
        ) from exc


@router.post(
    "/stage",
    response_model=SourceStagingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def stage_source_pdf(
    upload: Annotated[UploadFile, File()],
    manifest: Annotated[DocumentManifestEntry, Depends(get_pdf_staging_manifest)],
    repository: Annotated[
        IngestionRepository,
        Depends(get_pdf_staging_repository),
    ],
    storage: Annotated[
        KnowledgeBaseStorage,
        Depends(get_pdf_staging_storage),
    ],
    max_bytes: Annotated[int, Depends(get_pdf_staging_max_bytes)],
) -> SourceStagingResponse:
    try:
        payload = await upload.read(max_bytes + 1)
    finally:
        await upload.close()

    operation = partial(
        stage_pdf_upload,
        manifest=manifest,
        filename=upload.filename or "",
        content_type=upload.content_type,
        payload=payload,
        max_bytes=max_bytes,
        repository=repository,
        storage=storage,
    )

    try:
        result = await asyncio.to_thread(operation)
    except PdfStagingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except PdfStagingProtectedSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This manifest source is protected from staging.",
        ) from exc
    except PdfStagingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The PDF or manifest source is already registered.",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to stage source PDF")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stage source PDF.",
        ) from exc

    return SourceStagingResponse(
        database_document_id=result.database_document_id,
        manifest_id=result.manifest_id,
        safe_filename=result.safe_filename,
        checksum_sha256=result.checksum_sha256,
        size_bytes=result.size_bytes,
        status=result.status,
    )
