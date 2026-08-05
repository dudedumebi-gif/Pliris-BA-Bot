from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID


class FeedbackTargetNotFoundError(LookupError):
    """Raised when an assistant message is not owned by the guest conversation."""


class FeedbackRepository:
    """Persist session-owned, response-level feedback atomically."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], AbstractContextManager[Any]] | None = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection
        self.connection_factory = connection_factory

    async def upsert(
        self,
        *,
        client_session_id: str,
        assistant_message_id: UUID,
        rating: int,
        citation_helpful: bool | None = None,
        scope_decision_correct: bool | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        session_id = client_session_id.strip()
        if not session_id:
            raise ValueError("client_session_id must not be blank")
        if type(rating) is not int or rating not in {-1, 1}:
            raise ValueError("rating must be -1 or 1")

        normalized_comment = comment.strip() if comment is not None else None
        if not normalized_comment:
            normalized_comment = None
        if normalized_comment is not None and len(normalized_comment) > 1000:
            raise ValueError("comment must not exceed 1000 characters")

        return await asyncio.to_thread(
            self._upsert_sync,
            session_id,
            assistant_message_id,
            rating,
            citation_helpful,
            scope_decision_correct,
            normalized_comment,
        )

    def _upsert_sync(
        self,
        client_session_id: str,
        assistant_message_id: UUID,
        rating: int,
        citation_helpful: bool | None,
        scope_decision_correct: bool | None,
        comment: str | None,
    ) -> dict[str, Any]:
        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select m.conversation_id
                        from public.messages as m
                        join public.conversations as c
                          on c.id = m.conversation_id
                        where m.id = %s
                          and m.role = 'assistant'
                          and c.client_session_id = %s
                        for update
                        """,
                        (assistant_message_id, client_session_id),
                    )
                    target = cursor.fetchone()
                    if target is None:
                        raise FeedbackTargetNotFoundError(
                            "Feedback target was not found for this conversation."
                        )

                    cursor.execute(
                        """
                        insert into public.user_feedback (
                          conversation_id,
                          assistant_message_id,
                          rating,
                          citation_helpful,
                          scope_decision_correct,
                          comment
                        )
                        values (%s, %s, %s, %s, %s, %s)
                        on conflict (assistant_message_id)
                        do update set
                          conversation_id = excluded.conversation_id,
                          rating = excluded.rating,
                          citation_helpful = excluded.citation_helpful,
                          scope_decision_correct = excluded.scope_decision_correct,
                          comment = excluded.comment
                        returning
                          id,
                          assistant_message_id,
                          rating,
                          citation_helpful,
                          scope_decision_correct,
                          comment,
                          created_at
                        """,
                        (
                            target["conversation_id"],
                            assistant_message_id,
                            rating,
                            citation_helpful,
                            scope_decision_correct,
                            comment,
                        ),
                    )
                    feedback = cursor.fetchone()
                    if feedback is None:
                        raise RuntimeError("Feedback was not persisted.")

                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return dict(feedback)
