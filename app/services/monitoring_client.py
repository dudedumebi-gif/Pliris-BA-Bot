from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import httpx

from app.ui_config import UISettings

DEVELOPER_KEY_HEADER = "X-Pliris-Developer-Key"
_FORBIDDEN_FIELDS = {
    "authorization",
    "client_session_id",
    "content",
    "conversation_id",
    "developer_ui_access_key",
    "email",
    "guest_ui_shared_secret",
    "message",
    "message_id",
    "openai_api_key",
    "original_query",
    "prompt",
    "properties",
    "query",
    "rewritten_query",
    "session_id",
    "supabase_db_url",
    "supabase_secret_key",
    "token",
    "user_id",
}
_SUMMARY_INTEGER_FIELDS = (
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


class MonitoringDashboardServiceError(RuntimeError):
    """Safe developer-UI failure raised by the monitoring client."""

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.status_code = status_code


class MonitoringDashboardClient:
    """Server-to-server client for the protected aggregate dashboard."""

    def __init__(
        self,
        settings: UISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def get_dashboard(self, *, since_hours: int = 24) -> dict[str, Any]:
        if type(since_hours) is not int or not 1 <= since_hours <= 720:
            raise MonitoringDashboardServiceError(
                code="validation",
                user_message="The monitoring time range is not valid.",
            )

        payload = self._get(
            "/api/monitoring/dashboard",
            params={"since_hours": since_hours},
        )
        _validate_dashboard(payload, expected_hours=since_hours)
        return payload

    def _get(
        self,
        path: str,
        *,
        params: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        developer_key = self._settings.developer_ui_access_key
        if developer_key is None:
            raise MonitoringDashboardServiceError(
                code="not_configured",
                user_message="Developer monitoring access is not configured.",
            )

        try:
            with httpx.Client(
                timeout=self._settings.api_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.get(
                    f"{self._settings.api_url}{path}",
                    params=params,
                    headers={
                        DEVELOPER_KEY_HEADER: developer_key,
                        "Accept": "application/json",
                        "User-Agent": "pliris-developer-ui/0.1",
                    },
                )
        except httpx.TimeoutException as exc:
            raise MonitoringDashboardServiceError(
                code="timeout",
                user_message="Monitoring timed out. Please try again.",
            ) from exc
        except httpx.RequestError as exc:
            raise MonitoringDashboardServiceError(
                code="unavailable",
                user_message="Monitoring is temporarily unavailable.",
            ) from exc

        if response.status_code != 200:
            raise _service_error(response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise _invalid_payload_error() from exc
        if not isinstance(payload, dict) or _contains_forbidden_field(payload):
            raise _invalid_payload_error()
        return payload


def _validate_dashboard(payload: dict[str, Any], *, expected_hours: int) -> None:
    if payload.get("since_hours") != expected_hours:
        raise _invalid_payload_error()
    if payload.get("bucket") not in {"hour", "day"}:
        raise _invalid_payload_error()
    _validate_timestamp(payload.get("generated_at"))

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise _invalid_payload_error()
    for field in _SUMMARY_INTEGER_FIELDS:
        value = summary.get(field)
        if type(value) is not int or value < 0:
            raise _invalid_payload_error()
    for field in ("avg_latency_ms", "p95_latency_ms"):
        value = summary.get(field)
        if value is not None and not _is_non_negative_number(value):
            raise _invalid_payload_error()

    _validate_count_list(payload.get("response_timeline"), key="timestamp", timestamp=True)
    _validate_count_list(payload.get("scope_breakdown"), key="name")
    _validate_count_list(payload.get("latency_distribution"), key="label")
    _validate_count_list(payload.get("failure_breakdown"), key="name")

    model_usage = payload.get("model_usage")
    if not isinstance(model_usage, list):
        raise _invalid_payload_error()
    for item in model_usage:
        if not isinstance(item, dict) or not _non_empty_string(item.get("name")):
            raise _invalid_payload_error()
        for field in ("count", "input_tokens", "output_tokens"):
            value = item.get(field)
            if type(value) is not int or value < 0:
                raise _invalid_payload_error()


def _validate_count_list(value: Any, *, key: str, timestamp: bool = False) -> None:
    if not isinstance(value, list):
        raise _invalid_payload_error()
    for item in value:
        if not isinstance(item, dict):
            raise _invalid_payload_error()
        label = item.get(key)
        if timestamp:
            _validate_timestamp(label)
        elif not _non_empty_string(label):
            raise _invalid_payload_error()
        count = item.get("count")
        if type(count) is not int or count < 0:
            raise _invalid_payload_error()


def _validate_timestamp(value: Any) -> None:
    if not _non_empty_string(value):
        raise _invalid_payload_error()
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _invalid_payload_error() from exc


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_negative_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and value >= 0


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        if _FORBIDDEN_FIELDS.intersection(value):
            return True
        return any(_contains_forbidden_field(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _service_error(status_code: int) -> MonitoringDashboardServiceError:
    if status_code == 401:
        code = "not_authorized"
        message = "Developer monitoring access was not accepted."
    elif status_code == 422:
        code = "validation"
        message = "The monitoring time range is not valid."
    elif status_code in {502, 503, 504}:
        code = "unavailable"
        message = "Monitoring is temporarily unavailable."
    elif status_code >= 500:
        code = "server_error"
        message = "Monitoring could not be loaded."
    else:
        code = "request_failed"
        message = "Monitoring request failed."
    return MonitoringDashboardServiceError(
        code=code,
        user_message=message,
        status_code=status_code,
    )


def _invalid_payload_error() -> MonitoringDashboardServiceError:
    return MonitoringDashboardServiceError(
        code="invalid_response",
        user_message="Monitoring returned an unreadable response.",
        status_code=200,
    )
