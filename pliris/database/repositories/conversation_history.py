from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any


class ConversationHistoryRepository:
    """Read bounded recent messages for one validated client session token."""

    def __init__(
        self,
        *,
        connection_factory: (Callable[[], AbstractContextManager[Any]] | None) = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection
        self.connection_factory = connection_factory

    async def get_recent_messages(
        self,
        client_session_id: str,
        *,
        limit: int = 6,
    ) -> list[dict[str, str]]:
        """Return recent user/assistant messages in chronological order."""

        if not 2 <= limit <= 12:
            raise ValueError("limit must be between 2 and 12")
        normalized_id = client_session_id.strip()
        if not normalized_id:
            return []

        return await asyncio.to_thread(
            self._get_recent_messages_sync,
            normalized_id,
            limit,
        )

    def _get_recent_messages_sync(
        self,
        client_session_id: str,
        limit: int,
    ) -> list[dict[str, str]]:
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    select m.role, m.content
                    from public.messages as m
                    join public.conversations as c
                      on c.id = m.conversation_id
                    where c.client_session_id = %s
                      and m.role in ('user', 'assistant')
                    order by m.created_at desc, m.id desc
                    limit %s
                    """,
                (client_session_id, limit),
            )
            rows = cursor.fetchall()

        return [
            {
                "role": str(row["role"]),
                "content": str(row["content"]),
            }
            for row in reversed(rows)
        ]
