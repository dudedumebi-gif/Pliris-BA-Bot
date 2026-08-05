from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.ui_config import UISettings

SESSION_HEADER = "X-Pliris-Session-ID"
UI_KEY_HEADER = "X-Pliris-UI-Key"


class FeedbackServiceError(RuntimeError):
    """Safe UI-facing failure raised by the feedback API client."""

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class FeedbackReceipt:
    """Validated feedback state returned by the API."""

    id: str
    assistant_message_id: str
    rating: int
    citation_helpful: bool | None
    scope_decision_correct: bool | None
    comment: str | None
    created_at: str
    status: str


class FeedbackClient:
    """Synchronous server-to-server client for response feedback."""

    def __init__(
        self,
        settings: UISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def submit(
        self,
        *,
        conversation_id: str,
        assistant_message_id: str,
        rating: int,
        session_id: str,
        citation_helpful: bool | None = None,
        scope_decision_correct: bool | None = None,
        comment: str | None = None,
    ) -> FeedbackReceipt:
        """Create or replace feedback for one persisted assistant message."""

        headers = {
            SESSION_HEADER: session_id,
            "Accept": "application/json",
            "User-Agent": "pliris-streamlit-ui/0.1",
        }
        if self._settings.guest_ui_shared_secret is not None:
            headers[UI_KEY_HEADER] = self._settings.guest_ui_shared_secret

        try:
            with httpx.Client(
                timeout=self._settings.api_timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{self._settings.api_url}/api/feedback/",
                    headers=headers,
                    json={
                        "conversation_id": conversation_id,
                        "assistant_message_id": assistant_message_id,
                        "rating": rating,
                        "citation_helpful": citation_helpful,
                        "scope_decision_correct": scope_decision_correct,
                        "comment": _normalized_comment(comment),
                    },
                )
        except httpx.TimeoutException as exc:
            raise FeedbackServiceError(
                code="timeout",
                user_message="Feedback submission timed out. Please try again.",
            ) from exc
        except httpx.RequestError as exc:
            raise FeedbackServiceError(
                code="unavailable",
                user_message="Feedback is temporarily unavailable. Please try again shortly.",
            ) from exc

        if response.status_code != 200:
            raise _service_error_from_response(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise _invalid_payload_error() from exc

        return _parse_receipt(payload)


def _parse_receipt(payload: Any) -> FeedbackReceipt:
    if not isinstance(payload, dict):
        raise _invalid_payload_error()

    feedback_id = payload.get("id")
    assistant_message_id = payload.get("assistant_message_id")
    rating = payload.get("rating")
    citation_helpful = payload.get("citation_helpful")
    scope_decision_correct = payload.get("scope_decision_correct")
    comment = payload.get("comment")
    created_at = payload.get("created_at")
    status = payload.get("status")

    if not isinstance(feedback_id, str) or not feedback_id:
        raise _invalid_payload_error()
    if not isinstance(assistant_message_id, str) or not assistant_message_id:
        raise _invalid_payload_error()
    if rating not in {-1, 1}:
        raise _invalid_payload_error()
    if citation_helpful is not None and not isinstance(citation_helpful, bool):
        raise _invalid_payload_error()
    if scope_decision_correct is not None and not isinstance(scope_decision_correct, bool):
        raise _invalid_payload_error()
    if comment is not None and not isinstance(comment, str):
        raise _invalid_payload_error()
    if not isinstance(created_at, str) or not created_at:
        raise _invalid_payload_error()
    if status != "submitted":
        raise _invalid_payload_error()

    return FeedbackReceipt(
        id=feedback_id,
        assistant_message_id=assistant_message_id,
        rating=rating,
        citation_helpful=citation_helpful,
        scope_decision_correct=scope_decision_correct,
        comment=comment,
        created_at=created_at,
        status=status,
    )


def _service_error_from_response(response: httpx.Response) -> FeedbackServiceError:
    status_code = response.status_code

    if status_code == 400:
        code = "bad_request"
        message = "That feedback request is no longer valid."
    elif status_code == 403:
        code = "not_authorized"
        message = "This feedback session is no longer authorized."
    elif status_code == 404:
        code = "target_not_found"
        message = "That response is no longer available for feedback."
    elif status_code == 422:
        code = "validation"
        message = "The feedback could not be validated. Please revise it and try again."
    elif status_code == 429:
        code = "rate_limited"
        message = "Too many requests. Please wait before submitting feedback again."
    elif status_code in {502, 503, 504}:
        code = "unavailable"
        message = "Feedback is temporarily unavailable. Please try again shortly."
    elif status_code >= 500:
        code = "server_error"
        message = "Feedback could not be saved right now. Please try again."
    else:
        code = "request_failed"
        message = "Feedback could not be submitted. Please try again."

    return FeedbackServiceError(
        code=code,
        user_message=message,
        status_code=status_code,
        retry_after_seconds=_retry_after_seconds(response),
    )


def _retry_after_seconds(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None

    try:
        seconds = int(value)
    except ValueError:
        return None

    return seconds if seconds >= 0 else None


def _normalized_comment(comment: str | None) -> str | None:
    if comment is None:
        return None
    normalized = comment.strip()
    return normalized or None


def _invalid_payload_error() -> FeedbackServiceError:
    return FeedbackServiceError(
        code="invalid_response",
        user_message="Feedback returned an unreadable response. Please try again.",
        status_code=200,
    )
