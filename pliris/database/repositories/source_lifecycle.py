from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from uuid import UUID


class SourceNotFoundError(LookupError):
    """Raised when a requested source does not exist."""


class SourceConfirmationError(ValueError):
    """Raised when lifecycle confirmation does not match the source."""


class SourceLifecycleConflictError(RuntimeError):
    """Raised when a lifecycle transition is not currently valid."""


class SourceLifecycleRepository:
    """Atomic archive/restore transitions with append-only audit events."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], AbstractContextManager[Any]] | None = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection
        self.connection_factory = connection_factory

    async def archive(
        self,
        document_id: UUID,
        *,
        reason: str,
        confirmation: str,
        actor: str = "developer-api",
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._transition_sync,
            document_id,
            "archive",
            reason,
            confirmation,
            actor,
        )

    async def restore(
        self,
        document_id: UUID,
        *,
        reason: str,
        confirmation: str,
        actor: str = "developer-api",
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._transition_sync,
            document_id,
            "restore",
            reason,
            confirmation,
            actor,
        )

    async def list_events(
        self,
        document_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        return await asyncio.to_thread(
            self._list_events_sync,
            document_id,
            limit,
            offset,
        )

    def _transition_sync(
        self,
        document_id: UUID,
        action: str,
        reason: str,
        confirmation: str,
        actor: str,
    ) -> dict[str, Any]:
        normalized_reason = reason.strip()
        normalized_confirmation = confirmation.strip()
        normalized_actor = actor.strip()

        if not 10 <= len(normalized_reason) <= 500:
            raise ValueError("reason must be between 10 and 500 characters")
        if not normalized_actor or len(normalized_actor) > 100:
            raise ValueError("actor must be between 1 and 100 characters")
        if action not in {"archive", "restore"}:
            raise ValueError("unsupported lifecycle action")

        expected_status = "ready" if action == "archive" else "archived"
        new_status = "archived" if action == "archive" else "ready"

        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                select id, manifest_id, title, status
                from public.documents
                where id = %s
                for update
                """,
                (document_id,),
            )
            document = cursor.fetchone()
            if document is None:
                raise SourceNotFoundError("Source not found.")

            expected_confirmation = str(document.get("manifest_id") or document["id"])
            if not secrets.compare_digest(
                normalized_confirmation,
                expected_confirmation,
            ):
                raise SourceConfirmationError("Source confirmation did not match.")

            current_status = str(document["status"])
            if current_status != expected_status:
                raise SourceLifecycleConflictError(
                    f"Source must be {expected_status!r} before {action}."
                )

            if action == "restore":
                cursor.execute(
                    """
                    select
                      count(*)::int as chunk_count,
                      count(*) filter (
                        where embedding is not null
                      )::int as embedded_chunk_count
                    from public.document_chunks
                    where document_id = %s
                    """,
                    (document_id,),
                )
                readiness = cursor.fetchone() or {}
                chunk_count = int(readiness.get("chunk_count") or 0)
                embedded_count = int(readiness.get("embedded_chunk_count") or 0)
                if chunk_count < 1 or embedded_count != chunk_count:
                    raise SourceLifecycleConflictError("Archived source is not fully indexed.")

            cursor.execute(
                """
                update public.documents
                set status = %s
                where id = %s
                """,
                (new_status, document_id),
            )

            metadata = json.dumps(
                {
                    "manifest_id": document.get("manifest_id"),
                    "title": document.get("title"),
                    "confirmation_type": (
                        "manifest_id" if document.get("manifest_id") else "document_id"
                    ),
                }
            )
            cursor.execute(
                """
                insert into public.source_admin_events (
                  document_id,
                  action,
                  actor,
                  reason,
                  previous_status,
                  new_status,
                  metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s::jsonb)
                returning
                  id,
                  document_id,
                  action,
                  actor,
                  reason,
                  previous_status,
                  new_status,
                  metadata,
                  created_at
                """,
                (
                    document_id,
                    action,
                    normalized_actor,
                    normalized_reason,
                    current_status,
                    new_status,
                    metadata,
                ),
            )
            event = cursor.fetchone()
            if event is None:
                raise RuntimeError("Lifecycle audit event was not created.")

        return dict(event)

    def _list_events_sync(
        self,
        document_id: UUID,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        with self.connection_factory() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                select count(*)::int as total
                from public.source_admin_events
                where document_id = %s
                """,
                (document_id,),
            )
            total_row = cursor.fetchone()
            total = int(total_row["total"]) if total_row else 0

            cursor.execute(
                """
                select
                  id,
                  document_id,
                  action,
                  actor,
                  reason,
                  previous_status,
                  new_status,
                  metadata,
                  created_at
                from public.source_admin_events
                where document_id = %s
                order by created_at desc, id desc
                limit %s offset %s
                """,
                (document_id, limit, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]

        return rows, total
