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

    async def list_feedback(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        rating: int | None = None,
        citation_helpful: bool | None = None,
        scope_decision_correct: bool | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List feedback with response context, without guest-session identifiers."""

        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be zero or greater")
        if rating is not None and (type(rating) is not int or rating not in {-1, 1}):
            raise ValueError("rating must be -1, 1, or None")
        if citation_helpful is not None and type(citation_helpful) is not bool:
            raise ValueError("citation_helpful must be a boolean or None")
        if scope_decision_correct is not None and type(scope_decision_correct) is not bool:
            raise ValueError("scope_decision_correct must be a boolean or None")

        return await asyncio.to_thread(
            self._list_feedback_sync,
            limit,
            offset,
            rating,
            citation_helpful,
            scope_decision_correct,
        )

    def _list_feedback_sync(
        self,
        limit: int,
        offset: int,
        rating: int | None,
        citation_helpful: bool | None,
        scope_decision_correct: bool | None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions: list[str] = []
        parameters: list[Any] = []
        if rating is not None:
            conditions.append("uf.rating = %s")
            parameters.append(rating)
        if citation_helpful is not None:
            conditions.append("uf.citation_helpful = %s")
            parameters.append(citation_helpful)
        if scope_decision_correct is not None:
            conditions.append("uf.scope_decision_correct = %s")
            parameters.append(scope_decision_correct)

        where_clause = ""
        if conditions:
            where_clause = " where " + " and ".join(conditions)

        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "select count(*)::int as total "
                        "from public.user_feedback as uf" + where_clause,
                        tuple(parameters),
                    )
                    count_row = cursor.fetchone()
                    total = int(count_row["total"]) if count_row is not None else 0

                    cursor.execute(
                        """
                        select
                          uf.id,
                          uf.assistant_message_id,
                          uf.rating,
                          uf.citation_helpful,
                          uf.scope_decision_correct,
                          uf.comment,
                          previous_user.content as user_message,
                          assistant.content as assistant_message,
                          assistant.scope_status,
                          assistant.scope_confidence,
                          assistant.citations,
                          assistant.model_name,
                          assistant.input_tokens,
                          assistant.output_tokens,
                          assistant.latency_ms,
                          uf.created_at
                        from public.user_feedback as uf
                        join public.messages as assistant
                          on assistant.id = uf.assistant_message_id
                         and assistant.role = 'assistant'
                        left join lateral (
                          select candidate.content
                          from public.messages as candidate
                          where candidate.conversation_id = assistant.conversation_id
                            and candidate.role = 'user'
                            and candidate.created_at <= assistant.created_at
                          order by candidate.created_at desc, candidate.id desc
                          limit 1
                        ) as previous_user on true
                        """
                        + where_clause
                        + " order by uf.created_at desc, uf.id desc limit %s offset %s",
                        (*parameters, limit, offset),
                    )
                    rows = cursor.fetchall()
            except Exception:
                connection.rollback()
                raise

        return [dict(row) for row in rows], total

    async def get_stats(self) -> dict[str, Any]:
        """Return aggregate feedback counts for the protected developer workspace."""

        return await asyncio.to_thread(self._get_stats_sync)

    def _get_stats_sync(self) -> dict[str, Any]:
        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        select
                          count(*)::int as total_feedback,
                          count(*) filter (where rating = 1)::int as helpful_feedback,
                          count(*) filter (where rating = -1)::int as unhelpful_feedback,
                          count(*) filter (
                            where nullif(btrim(comment), '') is not null
                          )::int as commented_feedback,
                          count(*) filter (
                            where citation_helpful is not null
                          )::int as citation_ratings,
                          count(*) filter (
                            where citation_helpful is true
                          )::int as citation_helpful,
                          count(*) filter (
                            where scope_decision_correct is not null
                          )::int as scope_ratings,
                          count(*) filter (
                            where scope_decision_correct is true
                          )::int as scope_correct,
                          max(created_at) as latest_feedback_at
                        from public.user_feedback
                        """
                    )
                    row = cursor.fetchone()
            except Exception:
                connection.rollback()
                raise

        if row is None:
            raise RuntimeError("Feedback statistics were not returned.")
        return dict(row)
