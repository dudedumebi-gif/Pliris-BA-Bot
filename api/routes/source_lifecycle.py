from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.developer_access import require_developer_access
from api.schemas.source_lifecycle import (
    SourceLifecycleEvent,
    SourceLifecycleEventListResponse,
    SourceLifecycleRequest,
)
from pliris.database.repositories.source_lifecycle import (
    SourceConfirmationError,
    SourceLifecycleConflictError,
    SourceLifecycleRepository,
    SourceNotFoundError,
)

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_developer_access)])


def get_source_lifecycle_repository() -> SourceLifecycleRepository:
    return SourceLifecycleRepository()


@router.get(
    "/{source_id}/events",
    response_model=SourceLifecycleEventListResponse,
)
async def list_source_events(
    source_id: UUID,
    repository: Annotated[
        SourceLifecycleRepository,
        Depends(get_source_lifecycle_repository),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SourceLifecycleEventListResponse:
    try:
        items, total = await repository.list_events(
            source_id,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        logger.exception("Failed to list source lifecycle events")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch source lifecycle events.",
        ) from exc

    return SourceLifecycleEventListResponse(
        document_id=source_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{source_id}/archive",
    response_model=SourceLifecycleEvent,
)
async def archive_source(
    source_id: UUID,
    request: SourceLifecycleRequest,
    repository: Annotated[
        SourceLifecycleRepository,
        Depends(get_source_lifecycle_repository),
    ],
) -> SourceLifecycleEvent:
    return await _apply_action(
        source_id=source_id,
        request=request,
        repository=repository,
        action="archive",
    )


@router.post(
    "/{source_id}/restore",
    response_model=SourceLifecycleEvent,
)
async def restore_source(
    source_id: UUID,
    request: SourceLifecycleRequest,
    repository: Annotated[
        SourceLifecycleRepository,
        Depends(get_source_lifecycle_repository),
    ],
) -> SourceLifecycleEvent:
    return await _apply_action(
        source_id=source_id,
        request=request,
        repository=repository,
        action="restore",
    )


async def _apply_action(
    *,
    source_id: UUID,
    request: SourceLifecycleRequest,
    repository: SourceLifecycleRepository,
    action: str,
) -> SourceLifecycleEvent:
    try:
        if action == "archive":
            result = await repository.archive(
                source_id,
                reason=request.reason,
                confirmation=request.confirmation,
            )
        else:
            result = await repository.restore(
                source_id,
                reason=request.reason,
                confirmation=request.confirmation,
            )
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        ) from exc
    except SourceConfirmationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source confirmation did not match.",
        ) from exc
    except SourceLifecycleConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source lifecycle action conflicts with the current state.",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to apply source lifecycle action")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update source lifecycle.",
        ) from exc

    return SourceLifecycleEvent.model_validate(result)
