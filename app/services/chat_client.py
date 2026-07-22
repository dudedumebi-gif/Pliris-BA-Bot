from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.ui_config import UISettings

SESSION_HEADER = "X-Pliris-Session-ID"
UI_KEY_HEADER = "X-Pliris-UI-Key"


class ChatServiceError(RuntimeError):
    """Safe UI-facing failure raised by the chat API client."""

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
class ChatReply:
    """Validated response returned to the Streamlit chat page."""

    response: str
    citations: list[dict[str, Any]]
    confidence: float
    scope: str
    conversation_id: str | None
    metadata: dict[str, Any]


class ChatClient:
    """Synchronous server-to-server client for the public chat API."""

    def __init__(
        self,
        settings: UISettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport

    def send_message(
        self,
        *,
        message: str,
        conversation_id: str | None,
        session_id: str,
    ) -> ChatReply:
        """Send one guest message and return a validated chat response."""

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
                    f"{self._settings.api_url}/api/chat/",
                    headers=headers,
                    json={
                        "message": message,
                        "conversation_id": conversation_id,
                    },
                )
        except httpx.TimeoutException as exc:
            raise ChatServiceError(
                code="timeout",
                user_message=(
                    "Pliris is taking longer than expected. Please wait a moment and try again."
                ),
            ) from exc
        except httpx.RequestError as exc:
            raise ChatServiceError(
                code="unavailable",
                user_message=("Pliris is temporarily unavailable. Please try again shortly."),
            ) from exc

        if response.status_code != 200:
            raise _service_error_from_response(response)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ChatServiceError(
                code="invalid_response",
                user_message=("Pliris returned an unreadable response. Please try again."),
                status_code=response.status_code,
            ) from exc

        return _parse_reply(payload)


def _parse_reply(payload: Any) -> ChatReply:
    if not isinstance(payload, dict):
        raise _invalid_payload_error()

    response = payload.get("response")
    citations = payload.get("citations", [])
    confidence = payload.get("confidence")
    scope = payload.get("scope")
    conversation_id = payload.get("conversation_id")
    metadata = payload.get("metadata", {})

    if not isinstance(response, str) or not response.strip():
        raise _invalid_payload_error()
    if not isinstance(citations, list):
        raise _invalid_payload_error()
    if not isinstance(scope, str):
        raise _invalid_payload_error()
    if conversation_id is not None and not isinstance(conversation_id, str):
        raise _invalid_payload_error()
    if not isinstance(metadata, dict):
        raise _invalid_payload_error()

    try:
        normalized_confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise _invalid_payload_error() from exc

    if not 0.0 <= normalized_confidence <= 1.0:
        raise _invalid_payload_error()

    normalized_citations = [citation for citation in citations if isinstance(citation, dict)]

    return ChatReply(
        response=response,
        citations=normalized_citations,
        confidence=normalized_confidence,
        scope=scope,
        conversation_id=conversation_id,
        metadata=metadata,
    )


def _service_error_from_response(response: httpx.Response) -> ChatServiceError:
    status_code = response.status_code
    detail = _safe_detail(response)

    if status_code == 400:
        if detail == "Potential prompt injection detected":
            message = (
                "That request could not be processed because it may contain "
                "instruction-override language. Please rephrase it as a "
                "Business Analysis, Business Systems Analysis, or Project "
                "Management question."
            )
            code = "guardrail"
        else:
            message = "Pliris could not process that request. Please revise it and try again."
            code = "bad_request"
    elif status_code == 403:
        message = (
            "The public chat is temporarily unavailable because its "
            "server connection is not authorized."
        )
        code = "not_authorized"
    elif status_code == 422:
        message = "Your message could not be validated. Please shorten or revise it and try again."
        code = "validation"
    elif status_code == 429:
        message = detail or "Too many requests. Please wait before trying again."
        code = "rate_limited"
    elif status_code in {502, 503, 504}:
        message = "Pliris is temporarily unavailable. Please try again shortly."
        code = "unavailable"
    elif status_code >= 500:
        message = "Pliris encountered a temporary processing problem. Please try again."
        code = "server_error"
    else:
        message = "Pliris could not complete that request. Please try again."
        code = "request_failed"

    return ChatServiceError(
        code=code,
        user_message=message,
        status_code=status_code,
        retry_after_seconds=_retry_after_seconds(response),
    )


def _safe_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    detail = payload.get("detail")
    return detail if isinstance(detail, str) else None


def _retry_after_seconds(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None

    try:
        seconds = int(value)
    except ValueError:
        return None

    return seconds if seconds >= 0 else None


def _invalid_payload_error() -> ChatServiceError:
    return ChatServiceError(
        code="invalid_response",
        user_message=("Pliris returned an incomplete response. Please try again."),
        status_code=200,
    )
