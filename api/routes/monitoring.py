from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.developer_access import require_developer_access
from api.schemas.monitoring import MonitoringEventListResponse
from pliris.database.repositories.monitoring import MonitoringRepository
from pliris.monitoring.contracts import validate_event_type

logger = logging.getLogger(__name__)

router = APIRouter()


@lru_cache
def get_monitoring_repository() -> MonitoringRepository:
    """Return the process-level monitoring repository."""

    return MonitoringRepository()


@router.get(
    "/events",
    response_model=MonitoringEventListResponse,
    dependencies=[Depends(require_developer_access)],
)
async def list_monitoring_events(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    since_hours: Annotated[int, Query(ge=1, le=720)] = 24,
    event_type: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    severity: Annotated[
        Literal["debug", "info", "warning", "error", "critical"] | None,
        Query(),
    ] = None,
    repository: MonitoringRepository = Depends(get_monitoring_repository),
) -> MonitoringEventListResponse:
    """List protected operational events without raw prompts or guest identifiers."""

    try:
        normalized_type = validate_event_type(event_type) if event_type is not None else None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid monitoring event type.",
        ) from exc

    try:
        items, total = await repository.list_events(
            limit=limit,
            offset=offset,
            since_hours=since_hours,
            event_type=normalized_type,
            severity=severity,
        )
        return MonitoringEventListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            since_hours=since_hours,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid monitoring event filter.",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to list monitoring events")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch monitoring events.",
        ) from exc
