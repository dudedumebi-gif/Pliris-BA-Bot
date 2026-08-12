from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import httpx

from app.ui_config import UISettings

DEVELOPER_KEY_HEADER = "X-Pliris-Developer-Key"
EXPECTED_CHECKS = {"api_process", "supabase_data_api", "postgres"}
CONFIGURATION_FIELDS = {
    "app_name",
    "app_env",
    "chat_model",
    "embedding_model",
    "embedding_dimensions",
    "storage_bucket",
    "monitoring_enabled",
    "feedback_enabled",
}
FORBIDDEN_FIELDS = {
    "authorization",
    "client_session_id",
    "conversation_id",
    "developer_ui_access_key",
    "email",
    "error",
    "errors",
    "exception",
    "guest_ui_shared_secret",
    "message",
    "message_id",
    "openai_api_key",
    "prompt",
    "session_id",
    "stack_trace",
    "supabase_db_url",
    "supabase_publishable_key",
    "supabase_secret_key",
    "token",
    "traceback",
    "user_id",
}


class HealthDiagnosticsServiceError(RuntimeError):
    """Safe developer-UI failure raised by the health client."""

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


class HealthDiagnosticsClient:
    """Server-to-server client for protected API diagnostics."""

    def __init__(
        self,
        settings: UISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def get_diagnostics(self) -> dict[str, Any]:
        developer_key = self._settings.developer_ui_access_key
        if developer_key is None:
            raise HealthDiagnosticsServiceError(
                code="not_configured",
                user_message="Developer health access is not configured.",
            )

        try:
            with httpx.Client(
                timeout=self._settings.api_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.get(
                    f"{self._settings.api_url}/health/diagnostics",
                    headers={
                        DEVELOPER_KEY_HEADER: developer_key,
                        "Accept": "application/json",
                        "User-Agent": "pliris-developer-ui/0.1",
                    },
                )
        except httpx.TimeoutException as exc:
            raise HealthDiagnosticsServiceError(
                code="timeout",
                user_message="Health diagnostics timed out. Please try again.",
            ) from exc
        except httpx.RequestError as exc:
            raise HealthDiagnosticsServiceError(
                code="unavailable",
                user_message="Health diagnostics are temporarily unavailable.",
            ) from exc

        if response.status_code not in {200, 503}:
            raise _service_error(response.status_code)

        try:
            payload = response.json()
        except ValueError as exc:
            if response.status_code == 503:
                raise _service_error(503) from exc
            raise _invalid_payload_error() from exc

        try:
            _validate_diagnostics(payload, status_code=response.status_code)
        except HealthDiagnosticsServiceError as exc:
            if response.status_code == 503:
                raise _service_error(503) from exc
            raise
        return payload


def _validate_diagnostics(payload: Any, *, status_code: int) -> None:
    if not isinstance(payload, dict) or _contains_forbidden_field(payload):
        raise _invalid_payload_error()
    if set(payload) != {"status", "checked_at", "checks", "configuration"}:
        raise _invalid_payload_error()
    if payload["status"] not in {"ready", "not_ready"}:
        raise _invalid_payload_error()
    _validate_timestamp(payload["checked_at"])

    checks = payload["checks"]
    if not isinstance(checks, list) or len(checks) != len(EXPECTED_CHECKS):
        raise _invalid_payload_error()
    names: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) != {
            "name",
            "status",
            "latency_ms",
        }:
            raise _invalid_payload_error()
        name = check["name"]
        if name not in EXPECTED_CHECKS or name in names:
            raise _invalid_payload_error()
        names.add(name)
        if check["status"] not in {"healthy", "unavailable"}:
            raise _invalid_payload_error()
        if not _is_non_negative_number(check["latency_ms"]):
            raise _invalid_payload_error()
    if names != EXPECTED_CHECKS:
        raise _invalid_payload_error()

    expected_status = (
        "ready" if all(check["status"] == "healthy" for check in checks) else "not_ready"
    )
    if payload["status"] != expected_status:
        raise _invalid_payload_error()
    if (status_code == 200) != (payload["status"] == "ready"):
        raise _invalid_payload_error()

    configuration = payload["configuration"]
    if not isinstance(configuration, dict) or set(configuration) != CONFIGURATION_FIELDS:
        raise _invalid_payload_error()
    for field in (
        "app_name",
        "app_env",
        "chat_model",
        "embedding_model",
        "storage_bucket",
    ):
        if not _non_empty_string(configuration[field]):
            raise _invalid_payload_error()
    dimensions = configuration["embedding_dimensions"]
    if type(dimensions) is not int or dimensions < 1:
        raise _invalid_payload_error()
    for field in ("monitoring_enabled", "feedback_enabled"):
        if type(configuration[field]) is not bool:
            raise _invalid_payload_error()


def _validate_timestamp(value: Any) -> None:
    if not _non_empty_string(value):
        raise _invalid_payload_error()
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _invalid_payload_error() from exc


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        if FORBIDDEN_FIELDS.intersection(value):
            return True
        return any(_contains_forbidden_field(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_negative_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value) and value >= 0


def _service_error(status_code: int) -> HealthDiagnosticsServiceError:
    if status_code == 401:
        code = "not_authorized"
        message = "Developer health access was not accepted."
    elif status_code in {502, 503, 504}:
        code = "unavailable"
        message = "Health diagnostics are temporarily unavailable."
    elif status_code >= 500:
        code = "server_error"
        message = "Health diagnostics could not be loaded."
    else:
        code = "request_failed"
        message = "Health diagnostics request failed."
    return HealthDiagnosticsServiceError(
        code=code,
        user_message=message,
        status_code=status_code,
    )


def _invalid_payload_error() -> HealthDiagnosticsServiceError:
    return HealthDiagnosticsServiceError(
        code="invalid_response",
        user_message="Health diagnostics returned an unreadable response.",
        status_code=200,
    )
