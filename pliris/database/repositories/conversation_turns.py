from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ConversationTurnOutcome:
    """Identifiers created for one persisted non-grounded chat response."""

    client_session_id: str
    database_conversation_id: str
    user_message_id: str
    assistant_message_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "client_session_id": self.client_session_id,
            "database_conversation_id": self.database_conversation_id,
            "user_message_id": self.user_message_id,
            "assistant_message_id": self.assistant_message_id,
        }


class ConversationTurnRepository:
    """Persist non-grounded user/assistant turns for session continuation."""

    def __init__(
        self,
        *,
        connection_factory: (Callable[[], AbstractContextManager[Any]] | None) = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection
        self.connection_factory = connection_factory

    async def persist_turn(
        self,
        *,
        client_session_id: str,
        user_message: str,
        assistant_message: str,
        scope_status: str,
        scope_confidence: float,
    ) -> ConversationTurnOutcome:
        """Persist one bounded conversational turn without retrieval data."""

        session_id = client_session_id.strip()
        if not session_id:
            raise ValueError("client_session_id must not be blank")
        if not user_message.strip():
            raise ValueError("user_message must not be blank")
        if not assistant_message.strip():
            raise ValueError("assistant_message must not be blank")

        return await asyncio.to_thread(
            self._persist_turn_sync,
            session_id,
            user_message.strip(),
            assistant_message.strip(),
            scope_status.strip() or "borderline",
            max(0.0, min(float(scope_confidence), 1.0)),
        )

    def _persist_turn_sync(
        self,
        client_session_id: str,
        user_message: str,
        assistant_message: str,
        scope_status: str,
        scope_confidence: float,
    ) -> ConversationTurnOutcome:
        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select id
                        from public.conversations
                        where client_session_id = %s
                        order by created_at
                        limit 1
                        """,
                        (client_session_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        conversation_id = row["id"]
                    else:
                        cursor.execute(
                            """
                            insert into public.conversations (
                                client_session_id,
                                title
                            )
                            values (%s, %s)
                            returning id
                            """,
                            (
                                client_session_id,
                                user_message[:160],
                            ),
                        )
                        conversation_id = cursor.fetchone()["id"]

                    cursor.execute(
                        """
                        insert into public.messages (
                            conversation_id,
                            role,
                            content,
                            scope_status,
                            scope_confidence,
                            citations
                        )
                        values (%s, 'user', %s, %s, %s, '[]'::jsonb)
                        returning id
                        """,
                        (
                            conversation_id,
                            user_message,
                            scope_status,
                            scope_confidence,
                        ),
                    )
                    user_message_id = cursor.fetchone()["id"]
                    cursor.execute(
                        """
                        insert into public.messages (
                            conversation_id,
                            role,
                            content,
                            scope_status,
                            scope_confidence,
                            citations
                        )
                        values (
                            %s,
                            'assistant',
                            %s,
                            %s,
                            %s,
                            '[]'::jsonb
                        )
                        returning id
                        """,
                        (
                            conversation_id,
                            assistant_message,
                            scope_status,
                            scope_confidence,
                        ),
                    )
                    assistant_message_id = cursor.fetchone()["id"]
                    cursor.execute(
                        """
                        update public.conversations
                        set updated_at = now()
                        where id = %s
                        """,
                        (conversation_id,),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return ConversationTurnOutcome(
            client_session_id=client_session_id,
            database_conversation_id=str(conversation_id),
            user_message_id=str(user_message_id),
            assistant_message_id=str(assistant_message_id),
        )
