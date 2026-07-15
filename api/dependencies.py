import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pliris.config.settings import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Verify API key from request headers."""
    if settings.disable_auth:
        return "system"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header"
        )

    token = credentials.credentials

    # In production, validate against a proper auth system
    if token != settings.api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    return token


async def get_current_user(api_key: str = Depends(verify_api_key)) -> dict:
    """Get current user from API key."""
    # In production, fetch user from database
    return {"id": "system", "name": "System User", "role": "admin"}


async def get_db_session():
    """Get database session."""
    from pliris.database.postgres import get_session

    async for session in get_session():
        yield session
