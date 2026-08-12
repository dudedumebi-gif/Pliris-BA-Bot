from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from psycopg import Connection

from api.guest_access import get_guest_user
from pliris.database.postgres import postgres_connection


async def get_current_user(
    user: Annotated[dict[str, str], Depends(get_guest_user)],
) -> dict[str, str]:
    """Return the validated anonymous request identity."""

    return user


def get_db_session() -> Iterator[Connection]:
    """Yield one pooled PostgreSQL connection for API dependencies."""

    with postgres_connection() as connection:
        yield connection
