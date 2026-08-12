from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.ui_config import UISettings

DEVELOPER_KEY_HEADER = "X-Pliris-Developer-Key"
_FORBIDDEN_FIELDS = {
    "client_session_id",
    "conversation_id",
    "developer_ui_access_key",
    "guest_ui_shared_secret",
    "openai_api_key",
    "supabase_db_url",
    "supabase_secret_key",
}


class DeveloperFeedbackServiceError(RuntimeError):
    """Safe developer-UI failure raised by the feedback inspection client."""

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


@dataclass(frozen=True)
class DeveloperFeedbackPage:
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class DeveloperFeedbackClient:
    """Server-to-server client for protected feedback inspection."""

    def __init__(
        self,
        settings: UISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def get_stats(self) -> dict[str, Any]:
        payload = self._get("/api/feedback/stats")
        integer_fields = (
            "total_feedback",
            "helpful_feedback",
            "unhelpful_feedback",
            "commented_feedback",
            "citation_ratings",
            "citation_helpful",
            "scope_ratings",
            "scope_correct",
        )
        if any(type(payload.get(field)) is not int for field in integer_fields):
            raise _invalid_payload_error()
        latest = payload.get("latest_feedback_at")
        if latest is not None and not isinstance(latest, str):
            raise _invalid_payload_error()
        return payload

    def list_feedback(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        rating: int | None = None,
        citation_helpful: bool | None = None,
        scope_decision_correct: bool | None = None,
    ) -> DeveloperFeedbackPage:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if rating is not None:
            params["rating"] = rating
        if citation_helpful is not None:
            params["citation_helpful"] = str(citation_helpful).lower()
        if scope_decision_correct is not None:
            params["scope_decision_correct"] = str(scope_decision_correct).lower()

        payload = self._get("/api/feedback/", params=params)
        items = payload.get("items")
        total = payload.get("total")
        returned_limit = payload.get("limit")
        returned_offset = payload.get("offset")
        if (
            not isinstance(items, list)
            or type(total) is not int
            or type(returned_limit) is not int
            or type(returned_offset) is not int
            or any(not isinstance(item, dict) for item in items)
        ):
            raise _invalid_payload_error()
        for item in items:
            _validate_item(item)

        return DeveloperFeedbackPage(
            items=items,
            total=total,
            limit=returned_limit,
            offset=returned_offset,
        )

    def _get(
        self,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        developer_key = self._settings.developer_ui_access_key
        if developer_key is None:
            raise DeveloperFeedbackServiceError(
                code="not_configured",
                user_message="Developer feedback access is not configured.",
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
            raise DeveloperFeedbackServiceError(
                code="timeout",
                user_message="Feedback inspection timed out. Please try again.",
            ) from exc
        except httpx.RequestError as exc:
            raise DeveloperFeedbackServiceError(
                code="unavailable",
                user_message="Feedback inspection is temporarily unavailable.",
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


def _validate_item(item: dict[str, Any]) -> None:
    required_strings = ("id", "assistant_message_id", "assistant_message", "created_at")
    if any(not isinstance(item.get(field), str) or not item[field] for field in required_strings):
        raise _invalid_payload_error()
    if item.get("rating") not in {-1, 1}:
        raise _invalid_payload_error()
    for field in ("citation_helpful", "scope_decision_correct"):
        value = item.get(field)
        if value is not None and type(value) is not bool:
            raise _invalid_payload_error()
    if not isinstance(item.get("citations"), list):
        raise _invalid_payload_error()


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        if _FORBIDDEN_FIELDS.intersection(value):
            return True
        return any(_contains_forbidden_field(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_field(item) for item in value)
    return False


def _service_error(status_code: int) -> DeveloperFeedbackServiceError:
    if status_code == 401:
        code = "not_authorized"
        message = "Developer feedback access was not accepted."
    elif status_code == 422:
        code = "validation"
        message = "The feedback filters are not valid."
    elif status_code in {502, 503, 504}:
        code = "unavailable"
        message = "Feedback inspection is temporarily unavailable."
    elif status_code >= 500:
        code = "server_error"
        message = "Feedback inspection could not be loaded."
    else:
        code = "request_failed"
        message = "Feedback inspection request failed."
    return DeveloperFeedbackServiceError(
        code=code,
        user_message=message,
        status_code=status_code,
    )


def _invalid_payload_error() -> DeveloperFeedbackServiceError:
    return DeveloperFeedbackServiceError(
        code="invalid_response",
        user_message="Feedback inspection returned an unreadable response.",
        status_code=200,
    )
