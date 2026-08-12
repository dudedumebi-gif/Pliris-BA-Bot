from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.developer_access import require_developer_access
from api.schemas.sources import (
    SourceChunkListResponse,
    SourceDetail,
    SourceListResponse,
    SourceStats,
    SourceStatus,
)
from pliris.database.repositories.documents import DocumentRepository

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_developer_access)])


def get_document_repository() -> DocumentRepository:
    return DocumentRepository()


@router.get("/", response_model=SourceListResponse)
async def list_sources(
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_status: Annotated[SourceStatus | None, Query(alias="status")] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
) -> SourceListResponse:
    try:
        items, total = await repository.list_documents(
            limit=limit,
            offset=offset,
            status=source_status,
            query=query,
        )
        return SourceListResponse(items=items, total=total, limit=limit, offset=offset)
    except Exception as exc:
        logger.exception("Failed to list source documents")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch source documents.",
        ) from exc


@router.get("/stats", response_model=SourceStats)
async def get_source_stats(
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> SourceStats:
    try:
        return SourceStats.model_validate(await repository.get_stats())
    except Exception as exc:
        logger.exception("Failed to fetch source statistics")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch source statistics.",
        ) from exc


@router.get("/{source_id}", response_model=SourceDetail)
async def get_source(
    source_id: UUID,
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> SourceDetail:
    try:
        source = await repository.get_by_id(source_id)
    except Exception as exc:
        logger.exception("Failed to fetch source details")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch source details.",
        ) from exc
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    return SourceDetail.model_validate(source)


@router.get("/{source_id}/chunks", response_model=SourceChunkListResponse)
async def get_source_chunks(
    source_id: UUID,
    repository: Annotated[DocumentRepository, Depends(get_document_repository)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SourceChunkListResponse:
    try:
        source = await repository.get_by_id(source_id)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found.")
        items, total = await repository.list_chunks(source_id, limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch source chunks")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch source chunks.",
        ) from exc
    return SourceChunkListResponse(
        document_id=source_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
