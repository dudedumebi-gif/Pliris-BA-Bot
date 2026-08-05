from __future__ import annotations

import json

import httpx
import pytest

from app.services.developer_feedback_client import (
    DEVELOPER_KEY_HEADER,
    DeveloperFeedbackClient,
    DeveloperFeedbackServiceError,
)
from app.ui_config import UIMode, UISettings


def _settings(*, developer_key: str | None = "developer-secret") -> UISettings:
    return UISettings(
        app_env="development",
        api_url="https://api.example.test",
        api_timeout_seconds=30.0,
        ui_mode=UIMode.DEVELOPER,
        guest_ui_shared_secret=None,
        developer_ui_access_key=developer_key,
    )


def _response(request: httpx.Request, payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status,
        request=request,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )


def _item() -> dict[str, object]:
    return {
        "id": "feedback-1",
        "assistant_message_id": "assistant-1",
        "rating": 1,
        "citation_helpful": True,
        "scope_decision_correct": True,
        "comment": "Useful.",
        "user_message": "Question",
        "assistant_message": "Answer",
        "scope_status": "in_scope",
        "scope_confidence": 0.9,
        "citations": [],
        "model_name": "gpt-5-mini",
        "input_tokens": 1,
        "output_tokens": 2,
        "latency_ms": 3,
        "created_at": "2026-08-05T00:00:00+00:00",
    }


def test_client_sends_developer_key_and_filters() -> None:
    observed: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["key"] = request.headers.get(DEVELOPER_KEY_HEADER)
        return _response(
            request,
            {"items": [_item()], "total": 1, "limit": 25, "offset": 0},
        )

    page = DeveloperFeedbackClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).list_feedback(
        limit=25,
        rating=1,
        citation_helpful=True,
        scope_decision_correct=False,
    )

    assert page.total == 1
    assert observed["key"] == "developer-secret"
    assert observed["url"] == (
        "https://api.example.test/api/feedback/?limit=25&offset=0&rating=1"
        "&citation_helpful=true&scope_decision_correct=false"
    )


def test_client_parses_stats() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(
            request,
            {
                "total_feedback": 2,
                "helpful_feedback": 1,
                "unhelpful_feedback": 1,
                "commented_feedback": 1,
                "citation_ratings": 1,
                "citation_helpful": 1,
                "scope_ratings": 1,
                "scope_correct": 1,
                "latest_feedback_at": "2026-08-05T00:00:00+00:00",
            },
        )

    stats = DeveloperFeedbackClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).get_stats()

    assert stats["total_feedback"] == 2


def test_client_rejects_missing_key_and_forbidden_fields() -> None:
    with pytest.raises(DeveloperFeedbackServiceError) as missing:
        DeveloperFeedbackClient(_settings(developer_key=None)).get_stats()
    assert missing.value.code == "not_configured"

    def handler(request: httpx.Request) -> httpx.Response:
        item = _item()
        item["client_session_id"] = "private-session"
        return _response(
            request,
            {"items": [item], "total": 1, "limit": 50, "offset": 0},
        )

    with pytest.raises(DeveloperFeedbackServiceError) as unsafe:
        DeveloperFeedbackClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).list_feedback()
    assert unsafe.value.code == "invalid_response"


def test_client_hides_service_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(request, {"detail": "private database detail"}, 500)

    with pytest.raises(DeveloperFeedbackServiceError) as caught:
        DeveloperFeedbackClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).get_stats()

    assert caught.value.code == "server_error"
    assert "private database detail" not in caught.value.user_message
