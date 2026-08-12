from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from pliris.config.settings import get_settings

DEVELOPER_KEY_HEADER = "X-Pliris-Developer-Key"


def get_expected_developer_key() -> str | None:
    configured = get_settings().developer_ui_access_key
    if configured is None:
        return None
    return configured.get_secret_value()


async def require_developer_access(
    candidate: Annotated[str | None, Header(alias=DEVELOPER_KEY_HEADER)] = None,
    expected: Annotated[str | None, Depends(get_expected_developer_key)] = None,
) -> None:
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Developer API access is not configured.",
        )
    if candidate is None or not hmac.compare_digest(candidate, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Developer API access was not accepted.",
        )
