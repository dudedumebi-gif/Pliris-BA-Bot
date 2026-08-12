from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from app.services.feedback_client import FeedbackClient, FeedbackServiceError
from app.ui_config import UIMode, UISettings


def settings() -> UISettings:
    return UISettings(
        app_env="test",
        api_url="https://api.example.test",
        api_timeout_seconds=30,
        ui_mode=UIMode.PUBLIC,
        guest_ui_shared_secret="ui-secret",
        developer_ui_access_key=None,
    )


def test_feedback_client_submits_response_bound_payload_and_headers() -> None:
    session_id = str(uuid4())
    assistant_message_id = str(uuid4())
    feedback_id = str(uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.example.test/api/feedback/"
        assert request.headers["X-Pliris-Session-ID"] == session_id
        assert request.headers["X-Pliris-UI-Key"] == "ui-secret"
        payload = __import__("json").loads(request.read())
        assert payload == {
            "conversation_id": "conversation-token",
            "assistant_message_id": assistant_message_id,
            "rating": 1,
            "citation_helpful": True,
            "scope_decision_correct": None,
            "comment": "Useful answer.",
        }
        return httpx.Response(
            200,
            json={
                "id": feedback_id,
                "assistant_message_id": assistant_message_id,
                "rating": 1,
                "citation_helpful": True,
                "scope_decision_correct": None,
                "comment": "Useful answer.",
                "created_at": "2026-08-05T12:00:00Z",
                "status": "submitted",
            },
        )

    receipt = FeedbackClient(
        settings(),
        transport=httpx.MockTransport(handler),
    ).submit(
        conversation_id="conversation-token",
        assistant_message_id=assistant_message_id,
        rating=1,
        session_id=session_id,
        citation_helpful=True,
        comment="  Useful answer.  ",
    )

    assert receipt.id == feedback_id
    assert receipt.assistant_message_id == assistant_message_id
    assert receipt.rating == 1
    assert receipt.status == "submitted"


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (400, "bad_request"),
        (403, "not_authorized"),
        (404, "target_not_found"),
        (422, "validation"),
        (429, "rate_limited"),
        (500, "server_error"),
    ],
)
def test_feedback_client_maps_failures_without_exposing_internals(
    status_code: int,
    expected_code: str,
) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            text="private database stack trace and secret",
            request=request,
        )
    )

    with pytest.raises(FeedbackServiceError) as error:
        FeedbackClient(settings(), transport=transport).submit(
            conversation_id="conversation-token",
            assistant_message_id=str(uuid4()),
            rating=-1,
            session_id=str(uuid4()),
        )

    assert error.value.code == expected_code
    assert "database stack trace" not in error.value.user_message
    assert "secret" not in error.value.user_message


def test_feedback_client_preserves_retry_after_for_rate_limit() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            429,
            headers={"Retry-After": "20"},
            request=request,
        )
    )

    with pytest.raises(FeedbackServiceError) as error:
        FeedbackClient(settings(), transport=transport).submit(
            conversation_id="conversation-token",
            assistant_message_id=str(uuid4()),
            rating=1,
            session_id=str(uuid4()),
        )

    assert error.value.retry_after_seconds == 20


def test_feedback_client_rejects_incomplete_success_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"status": "submitted", "rating": 1},
            request=request,
        )
    )

    with pytest.raises(FeedbackServiceError) as error:
        FeedbackClient(settings(), transport=transport).submit(
            conversation_id="conversation-token",
            assistant_message_id=str(uuid4()),
            rating=1,
            session_id=str(uuid4()),
        )

    assert error.value.code == "invalid_response"
