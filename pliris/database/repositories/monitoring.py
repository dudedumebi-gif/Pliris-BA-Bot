from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pliris.monitoring.contracts import (
    redact_event_properties,
    sanitize_event_properties,
    validate_event_type,
    validate_severity,
)
from pliris.monitoring.dashboard_queries import DashboardQueries


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


class MonitoringRepository:
    """Persist and inspect bounded operational events."""

    def __init__(
        self,
        *,
        connection_factory: Callable[[], AbstractContextManager[Any]] | None = None,
        json_wrapper: Callable[[Any], Any] | None = None,
    ) -> None:
        if connection_factory is None:
            from pliris.database.postgres import postgres_connection

            connection_factory = postgres_connection
        self.connection_factory = connection_factory
        self.json_wrapper = json_wrapper

    async def record_event(
        self,
        *,
        event_type: str,
        severity: str = "info",
        properties: dict[str, Any] | None = None,
        conversation_id: str | UUID | None = None,
        message_id: str | UUID | None = None,
    ) -> str:
        """Store one privacy-safe monitoring event."""

        normalized_type = validate_event_type(event_type)
        normalized_severity = validate_severity(severity)
        safe_properties = sanitize_event_properties(properties)
        normalized_conversation_id = self._optional_uuid(
            conversation_id,
            field_name="conversation_id",
        )
        normalized_message_id = self._optional_uuid(
            message_id,
            field_name="message_id",
        )

        return await asyncio.to_thread(
            self._record_event_sync,
            normalized_type,
            normalized_severity,
            safe_properties,
            normalized_conversation_id,
            normalized_message_id,
        )

    def _record_event_sync(
        self,
        event_type: str,
        severity: str,
        properties: dict[str, Any],
        conversation_id: UUID | None,
        message_id: UUID | None,
    ) -> str:
        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        insert into public.monitoring_events (
                            event_type,
                            conversation_id,
                            message_id,
                            severity,
                            properties
                        )
                        values (%s, %s, %s, %s, %s)
                        returning id
                        """,
                        (
                            event_type,
                            conversation_id,
                            message_id,
                            severity,
                            self._json(properties),
                        ),
                    )
                    row = cursor.fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        if row is None or row.get("id") is None:
            raise RuntimeError("Monitoring event identifier was not returned.")
        return str(row["id"])

    async def list_events(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        since_hours: int = 24,
        event_type: str | None = None,
        severity: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List a protected, privacy-safe projection of recent events."""

        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be zero or greater")
        if type(since_hours) is not int or not 1 <= since_hours <= 720:
            raise ValueError("since_hours must be between 1 and 720")

        normalized_type = validate_event_type(event_type) if event_type is not None else None
        normalized_severity = validate_severity(severity) if severity is not None else None
        return await asyncio.to_thread(
            self._list_events_sync,
            limit,
            offset,
            since_hours,
            normalized_type,
            normalized_severity,
        )

    def _list_events_sync(
        self,
        limit: int,
        offset: int,
        since_hours: int,
        event_type: str | None,
        severity: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = ["created_at >= now() - (%s * interval '1 hour')"]
        parameters: list[Any] = [since_hours]
        if event_type is not None:
            conditions.append("event_type = %s")
            parameters.append(event_type)
        if severity is not None:
            conditions.append("severity = %s")
            parameters.append(severity)
        where_clause = " where " + " and ".join(conditions)

        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "select count(*)::int as total "
                        "from public.monitoring_events" + where_clause,
                        tuple(parameters),
                    )
                    count_row = cursor.fetchone()
                    total = int(count_row["total"]) if count_row is not None else 0

                    cursor.execute(
                        """
                        select id, event_type, severity, properties, created_at
                        from public.monitoring_events
                        """
                        + where_clause
                        + " order by created_at desc, id desc limit %s offset %s",
                        (*parameters, limit, offset),
                    )
                    rows = cursor.fetchall()
            except Exception:
                connection.rollback()
                raise

        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["properties"] = redact_event_properties(item.get("properties"))
            items.append(item)
        return items, total


    async def get_dashboard(self, *, since_hours: int = 24) -> dict[str, Any]:
        """Return aggregate-only monitoring metrics for a bounded time window."""

        bucket = DashboardQueries.bucket_for_hours(since_hours)
        return await asyncio.to_thread(
            self._get_dashboard_sync,
            since_hours,
            bucket,
        )

    def _get_dashboard_sync(
        self,
        since_hours: int,
        bucket: str,
    ) -> dict[str, Any]:
        with self.connection_factory() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        DashboardQueries.SUMMARY,
                        (since_hours, since_hours, since_hours),
                    )
                    summary = cursor.fetchone() or {}

                    cursor.execute(
                        DashboardQueries.RESPONSE_TIMELINE,
                        (bucket, since_hours),
                    )
                    response_timeline = cursor.fetchall()

                    cursor.execute(
                        DashboardQueries.SCOPE_BREAKDOWN,
                        (since_hours,),
                    )
                    scope_breakdown = cursor.fetchall()

                    cursor.execute(
                        DashboardQueries.LATENCY_DISTRIBUTION,
                        (since_hours,),
                    )
                    latency_distribution = cursor.fetchall()

                    cursor.execute(
                        DashboardQueries.FAILURE_BREAKDOWN,
                        (since_hours,),
                    )
                    failure_breakdown = cursor.fetchall()

                    cursor.execute(
                        DashboardQueries.MODEL_USAGE,
                        (since_hours,),
                    )
                    model_usage = cursor.fetchall()
            except Exception:
                connection.rollback()
                raise

        integer_fields = (
            "total_responses",
            "active_conversations",
            "in_scope_responses",
            "borderline_responses",
            "out_of_scope_responses",
            "latency_samples",
            "input_tokens",
            "output_tokens",
            "token_samples",
            "feedback_records",
            "helpful_feedback",
            "unhelpful_feedback",
            "commented_feedback",
            "request_failures",
            "prompt_injection_blocks",
            "feedback_submissions",
        )
        normalized_summary = {
            field: int(summary.get(field) or 0) for field in integer_fields
        }
        normalized_summary.update(
            {
                "avg_latency_ms": _optional_float(summary.get("avg_latency_ms")),
                "p95_latency_ms": _optional_float(summary.get("p95_latency_ms")),
            }
        )

        return {
            "generated_at": datetime.now(UTC),
            "since_hours": since_hours,
            "bucket": bucket,
            "summary": normalized_summary,
            "response_timeline": [dict(row) for row in response_timeline],
            "scope_breakdown": [dict(row) for row in scope_breakdown],
            "latency_distribution": [dict(row) for row in latency_distribution],
            "failure_breakdown": [dict(row) for row in failure_breakdown],
            "model_usage": [dict(row) for row in model_usage],
        }

    async def log_event(self, event_type: str, data: dict[str, Any]) -> str:
        """Compatibility wrapper for internal event producers."""

        if not isinstance(data, dict):
            raise ValueError("event data must be an object")
        properties = dict(data)
        properties.pop("event_type", None)
        severity = properties.pop("severity", "info")
        conversation_id = properties.pop("conversation_id", None)
        message_id = properties.pop("message_id", None)
        return await self.record_event(
            event_type=event_type,
            severity=severity,
            properties=properties,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    async def get_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Compatibility wrapper for protected recent-event inspection."""

        items, _ = await self.list_events(limit=limit, event_type=event_type)
        return items

    def _json(self, value: Any) -> Any:
        if self.json_wrapper is not None:
            return self.json_wrapper(value)

        from psycopg.types.json import Jsonb

        return Jsonb(value)

    @staticmethod
    def _optional_uuid(
        value: str | UUID | None,
        *,
        field_name: str,
    ) -> UUID | None:
        if value is None:
            return None
        try:
            return value if isinstance(value, UUID) else UUID(value)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"{field_name} must be a UUID or None") from exc
