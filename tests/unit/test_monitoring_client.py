from __future__ import annotations

import json

import httpx
import pytest

from app.services.monitoring_client import (
    DEVELOPER_KEY_HEADER,
    MonitoringDashboardClient,
    MonitoringDashboardServiceError,
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


def _dashboard() -> dict[str, object]:
    return {
        "generated_at": "2026-08-06T08:00:00+00:00",
        "since_hours": 168,
        "bucket": "day",
        "summary": {
            "total_responses": 8,
            "active_conversations": 3,
            "in_scope_responses": 5,
            "borderline_responses": 1,
            "out_of_scope_responses": 2,
            "latency_samples": 5,
            "avg_latency_ms": 1250.5,
            "p95_latency_ms": 2800.0,
            "input_tokens": 1200,
            "output_tokens": 400,
            "token_samples": 5,
            "feedback_records": 3,
            "helpful_feedback": 2,
            "unhelpful_feedback": 1,
            "commented_feedback": 1,
            "request_failures": 1,
            "prompt_injection_blocks": 2,
            "feedback_submissions": 4,
        },
        "response_timeline": [{"timestamp": "2026-08-06T08:00:00+00:00", "count": 8}],
        "scope_breakdown": [{"name": "in_scope", "count": 5}],
        "latency_distribution": [{"label": "1-3s", "count": 4}],
        "failure_breakdown": [{"name": "chat.request_failed", "count": 1}],
        "model_usage": [
            {
                "name": "gpt-test",
                "count": 5,
                "input_tokens": 1200,
                "output_tokens": 400,
            }
        ],
    }


def test_client_sends_developer_key_and_requested_window() -> None:
    observed: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["key"] = request.headers.get(DEVELOPER_KEY_HEADER)
        return _response(request, _dashboard())

    result = MonitoringDashboardClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).get_dashboard(since_hours=168)

    assert result["summary"]["total_responses"] == 8
    assert observed["key"] == "developer-secret"
    assert observed["url"] == ("https://api.example.test/api/monitoring/dashboard?since_hours=168")


def test_client_rejects_missing_key_and_invalid_window() -> None:
    with pytest.raises(MonitoringDashboardServiceError) as missing:
        MonitoringDashboardClient(_settings(developer_key=None)).get_dashboard()
    assert missing.value.code == "not_configured"

    with pytest.raises(MonitoringDashboardServiceError) as invalid:
        MonitoringDashboardClient(_settings()).get_dashboard(since_hours=0)
    assert invalid.value.code == "validation"


def test_client_rejects_private_or_malformed_payloads() -> None:
    def private_handler(request: httpx.Request) -> httpx.Response:
        payload = _dashboard()
        payload["conversation_id"] = "private-conversation"
        return _response(request, payload)

    with pytest.raises(MonitoringDashboardServiceError) as private:
        MonitoringDashboardClient(
            _settings(),
            transport=httpx.MockTransport(private_handler),
        ).get_dashboard(since_hours=168)
    assert private.value.code == "invalid_response"

    def malformed_handler(request: httpx.Request) -> httpx.Response:
        payload = _dashboard()
        payload["summary"]["total_responses"] = -1
        return _response(request, payload)

    with pytest.raises(MonitoringDashboardServiceError) as malformed:
        MonitoringDashboardClient(
            _settings(),
            transport=httpx.MockTransport(malformed_handler),
        ).get_dashboard(since_hours=168)
    assert malformed.value.code == "invalid_response"


def test_client_hides_service_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(request, {"detail": "private database detail"}, 500)

    with pytest.raises(MonitoringDashboardServiceError) as caught:
        MonitoringDashboardClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).get_dashboard(since_hours=168)

    assert caught.value.code == "server_error"
    assert "private database detail" not in caught.value.user_message
