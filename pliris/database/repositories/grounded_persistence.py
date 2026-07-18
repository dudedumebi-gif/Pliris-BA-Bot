from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID, uuid4

from pliris.retrieval.models import RetrievedChunk

_ALLOWED_SCOPE_STATUSES = {
    "in_scope",
    "borderline",
    "out_of_scope",
}


@dataclass(frozen=True, slots=True)
class GroundedExchange:
    """Complete grounded interaction to persist in one transaction."""

    client_session_id: str | None
    user_id: str
    original_query: str
    assistant_response: str
    scope_status: str
    scope_confidence: float | None
    scope_category: str | None
    citations: tuple[dict[str, Any], ...]
    model_name: str
    input_tokens: int | None
    output_tokens: int | None
    total_latency_ms: float | int | None
    retrieval_latency_ms: float | int | None
    requested_match_count: int
    chunks: tuple[RetrievedChunk, ...]
    selected_chunk_ids: frozenset[str]
    insufficient_evidence: bool
    response_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PersistenceOutcome:
    """Identifiers created by one successful persistence transaction."""

    client_session_id: str
    database_conversation_id: str
    user_message_id: str
    assistant_message_id: str
    retrieval_query_id: str
    monitoring_event_id: str
    retrieval_result_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GroundedPersistenceRepository:
    """
    Persist one grounded interaction atomically through hosted PostgreSQL.

    The public method is asynchronous while the existing Psycopg connection
    pool is synchronous, so database work is moved to a worker thread.
    """

    def __init__(
        self,
        *,
        connection_factory: (Callable[[], AbstractContextManager[Any]] | None) = None,
        json_wrapper: Callable[[Any], Any] | None = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection

        self.connection_factory = connection_factory
        self.json_wrapper = json_wrapper

    async def persist_exchange(
        self,
        exchange: GroundedExchange,
    ) -> PersistenceOutcome:
        self._validate(exchange)
        return await asyncio.to_thread(
            self._persist_exchange_sync,
            exchange,
        )

    def _persist_exchange_sync(
        self,
        exchange: GroundedExchange,
    ) -> PersistenceOutcome:
        session_id = (
            exchange.client_session_id.strip() if exchange.client_session_id else str(uuid4())
        )
        scope_confidence = self._scope_confidence(exchange.scope_confidence)
        scope_confidence_basis = (
            "classifier_reported"
            if exchange.scope_confidence is not None
            else "validated_discrete_scope_decision"
        )

        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    conversation_id = self._resolve_conversation(
                        cursor,
                        client_session_id=session_id,
                        title=self._title(exchange.original_query),
                    )
                    user_message_id = self._insert_user_message(
                        cursor,
                        conversation_id=conversation_id,
                        exchange=exchange,
                        scope_confidence=scope_confidence,
                    )
                    retrieval_query_id = self._insert_retrieval_query(
                        cursor,
                        conversation_id=conversation_id,
                        user_message_id=user_message_id,
                        exchange=exchange,
                        scope_confidence=scope_confidence,
                    )
                    retrieval_result_count = self._insert_retrieval_results(
                        cursor,
                        retrieval_query_id=retrieval_query_id,
                        exchange=exchange,
                    )
                    assistant_message_id = self._insert_assistant_message(
                        cursor,
                        conversation_id=conversation_id,
                        exchange=exchange,
                        scope_confidence=scope_confidence,
                    )
                    monitoring_event_id = self._insert_monitoring_event(
                        cursor,
                        conversation_id=conversation_id,
                        message_id=assistant_message_id,
                        exchange=exchange,
                        scope_confidence=scope_confidence,
                        scope_confidence_basis=(scope_confidence_basis),
                        retrieval_result_count=(retrieval_result_count),
                    )
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

        return PersistenceOutcome(
            client_session_id=session_id,
            database_conversation_id=str(conversation_id),
            user_message_id=str(user_message_id),
            assistant_message_id=str(assistant_message_id),
            retrieval_query_id=str(retrieval_query_id),
            monitoring_event_id=str(monitoring_event_id),
            retrieval_result_count=retrieval_result_count,
        )

    def _resolve_conversation(
        self,
        cursor: Any,
        *,
        client_session_id: str,
        title: str,
    ) -> Any:
        cursor.execute(
            """
            select pg_advisory_xact_lock(
                hashtextextended(%s, 0)
            )
            """,
            (client_session_id,),
        )

        database_id = self._uuid_or_none(client_session_id)
        if database_id is not None:
            cursor.execute(
                """
                select id
                from public.conversations
                where id = %s
                   or client_session_id = %s
                order by
                    case when id = %s then 0 else 1 end,
                    created_at
                limit 1
                """,
                (
                    database_id,
                    client_session_id,
                    database_id,
                ),
            )
        else:
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
            cursor.execute(
                """
                update public.conversations
                set title = coalesce(title, %s),
                    updated_at = now()
                where id = %s
                """,
                (title, conversation_id),
            )
            return conversation_id

        cursor.execute(
            """
            insert into public.conversations (
                client_session_id,
                title
            )
            values (%s, %s)
            returning id
            """,
            (client_session_id, title),
        )
        return cursor.fetchone()["id"]

    def _insert_user_message(
        self,
        cursor: Any,
        *,
        conversation_id: Any,
        exchange: GroundedExchange,
        scope_confidence: float,
    ) -> Any:
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
            values (%s, 'user', %s, %s, %s, %s)
            returning id
            """,
            (
                conversation_id,
                exchange.original_query,
                exchange.scope_status,
                scope_confidence,
                self._json([]),
            ),
        )
        return cursor.fetchone()["id"]

    def _insert_retrieval_query(
        self,
        cursor: Any,
        *,
        conversation_id: Any,
        user_message_id: Any,
        exchange: GroundedExchange,
        scope_confidence: float,
    ) -> Any:
        cursor.execute(
            """
            insert into public.retrieval_queries (
                conversation_id,
                user_message_id,
                original_query,
                rewritten_query,
                scope_status,
                scope_confidence,
                retrieval_method,
                requested_match_count,
                latency_ms
            )
            values (
                %s, %s, %s, null, %s, %s,
                'hosted_hybrid_rrf', %s, %s
            )
            returning id
            """,
            (
                conversation_id,
                user_message_id,
                exchange.original_query,
                exchange.scope_status,
                scope_confidence,
                exchange.requested_match_count,
                self._milliseconds(exchange.retrieval_latency_ms),
            ),
        )
        return cursor.fetchone()["id"]

    def _insert_retrieval_results(
        self,
        cursor: Any,
        *,
        retrieval_query_id: Any,
        exchange: GroundedExchange,
    ) -> int:
        rows: list[tuple[Any, ...]] = []
        for chunk in exchange.chunks:
            rows.append(
                (
                    retrieval_query_id,
                    chunk.chunk_id,
                    chunk.rank,
                    chunk.score,
                    self._positive_int(chunk.metadata.get("semantic_rank")),
                    self._positive_int(chunk.metadata.get("keyword_rank")),
                    chunk.chunk_id in exchange.selected_chunk_ids,
                )
            )

        if not rows:
            return 0

        cursor.executemany(
            """
            insert into public.retrieval_results (
                retrieval_query_id,
                chunk_id,
                result_rank,
                hybrid_score,
                semantic_rank,
                keyword_rank,
                reranker_score,
                selected_for_context
            )
            values (%s, %s, %s, %s, %s, %s, null, %s)
            """,
            rows,
        )
        return len(rows)

    def _insert_assistant_message(
        self,
        cursor: Any,
        *,
        conversation_id: Any,
        exchange: GroundedExchange,
        scope_confidence: float,
    ) -> Any:
        cursor.execute(
            """
            insert into public.messages (
                conversation_id,
                role,
                content,
                scope_status,
                scope_confidence,
                citations,
                model_name,
                input_tokens,
                output_tokens,
                latency_ms
            )
            values (
                %s, 'assistant', %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            returning id
            """,
            (
                conversation_id,
                exchange.assistant_response,
                exchange.scope_status,
                scope_confidence,
                self._json(list(exchange.citations)),
                exchange.model_name,
                exchange.input_tokens,
                exchange.output_tokens,
                self._milliseconds(exchange.total_latency_ms),
            ),
        )
        return cursor.fetchone()["id"]

    def _insert_monitoring_event(
        self,
        cursor: Any,
        *,
        conversation_id: Any,
        message_id: Any,
        exchange: GroundedExchange,
        scope_confidence: float,
        scope_confidence_basis: str,
        retrieval_result_count: int,
    ) -> Any:
        properties = {
            **exchange.metadata,
            "user_id": exchange.user_id,
            "scope_status": exchange.scope_status,
            "scope_category": exchange.scope_category,
            "scope_confidence": scope_confidence,
            "scope_confidence_basis": scope_confidence_basis,
            "response_id": exchange.response_id,
            "insufficient_evidence": (exchange.insufficient_evidence),
            "retrieval_result_count": retrieval_result_count,
            "selected_context_count": len(exchange.selected_chunk_ids),
            "cited_chunk_ids": [
                citation.get("chunk_id")
                for citation in exchange.citations
                if citation.get("chunk_id")
            ],
        }
        cursor.execute(
            """
            insert into public.monitoring_events (
                event_type,
                conversation_id,
                message_id,
                severity,
                properties
            )
            values (
                'grounded_response_completed',
                %s,
                %s,
                'info',
                %s
            )
            returning id
            """,
            (
                conversation_id,
                message_id,
                self._json(properties),
            ),
        )
        return cursor.fetchone()["id"]

    def _json(self, value: Any) -> Any:
        if self.json_wrapper is not None:
            return self.json_wrapper(value)

        from psycopg.types.json import Jsonb

        return Jsonb(value)

    @staticmethod
    def _validate(exchange: GroundedExchange) -> None:
        if not exchange.original_query.strip():
            raise ValueError("original_query must not be blank.")
        if not exchange.assistant_response.strip():
            raise ValueError("assistant_response must not be blank.")
        if exchange.scope_status not in _ALLOWED_SCOPE_STATUSES:
            raise ValueError("scope_status must be in_scope, borderline, or out_of_scope.")
        if exchange.requested_match_count < 1:
            raise ValueError("requested_match_count must be positive.")
        if exchange.scope_confidence is not None and not (0.0 <= exchange.scope_confidence <= 1.0):
            raise ValueError("scope_confidence must be between 0 and 1.")

    @staticmethod
    def _scope_confidence(value: float | None) -> float:
        return 1.0 if value is None else float(value)

    @staticmethod
    def _milliseconds(value: float | int | None) -> int | None:
        if value is None:
            return None
        return max(0, round(float(value)))

    @staticmethod
    def _positive_int(value: Any) -> int | None:
        try:
            converted = int(value)
        except (TypeError, ValueError):
            return None
        return converted if converted > 0 else None

    @staticmethod
    def _uuid_or_none(value: str) -> UUID | None:
        try:
            return UUID(value)
        except (ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def _title(query: str) -> str:
        normalized = " ".join(query.split())
        if len(normalized) <= 160:
            return normalized
        return normalized[:157].rstrip() + "..."
