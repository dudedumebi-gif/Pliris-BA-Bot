from __future__ import annotations

import json

import httpx
import pytest

from app.services.health_client import (
    DEVELOPER_KEY_HEADER,
    HealthDiagnosticsClient,
    HealthDiagnosticsServiceError,
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


def _payload(*, ready: bool = True) -> dict[str, object]:
    return {
        "status": "ready" if ready else "not_ready",
        "checked_at": "2026-08-12T08:00:00+00:00",
        "checks": [
            {"name": "api_process", "status": "healthy", "latency_ms": 0.0},
            {
                "name": "supabase_data_api",
                "status": "healthy",
                "latency_ms": 21.5,
            },
            {
                "name": "postgres",
                "status": "healthy" if ready else "unavailable",
                "latency_ms": 18.0,
            },
        ],
        "configuration": {
            "app_name": "Pliris BA Bot",
            "app_env": "test",
            "chat_model": "gpt-test",
            "embedding_model": "embedding-test",
            "embedding_dimensions": 1536,
            "storage_bucket": "knowledge-base",
            "monitoring_enabled": True,
            "feedback_enabled": True,
        },
    }


def _response(
    request: httpx.Request,
    payload: object,
    status: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status,
        request=request,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )


def test_client_sends_developer_key_and_accepts_ready_payload() -> None:
    observed: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["key"] = request.headers.get(DEVELOPER_KEY_HEADER)
        return _response(request, _payload())

    result = HealthDiagnosticsClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).get_diagnostics()

    assert result["status"] == "ready"
    assert observed == {
        "url": "https://api.example.test/health/diagnostics",
        "key": "developer-secret",
    }


def test_client_accepts_structured_not_ready_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _response(request, _payload(ready=False), 503)

    result = HealthDiagnosticsClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).get_diagnostics()

    assert result["status"] == "not_ready"
    assert result["checks"][2]["status"] == "unavailable"


def test_client_rejects_missing_key_and_hides_service_details() -> None:
    with pytest.raises(HealthDiagnosticsServiceError) as missing:
        HealthDiagnosticsClient(_settings(developer_key=None)).get_diagnostics()
    assert missing.value.code == "not_configured"

    def handler(request: httpx.Request) -> httpx.Response:
        return _response(request, {"detail": "private credential detail"}, 500)

    with pytest.raises(HealthDiagnosticsServiceError) as failed:
        HealthDiagnosticsClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).get_diagnostics()
    assert failed.value.code == "server_error"
    assert "private credential detail" not in failed.value.user_message


def test_client_rejects_private_and_inconsistent_payloads() -> None:
    def private_handler(request: httpx.Request) -> httpx.Response:
        payload = _payload()
        payload["supabase_db_url"] = "postgresql://private"
        return _response(request, payload)

    with pytest.raises(HealthDiagnosticsServiceError) as private:
        HealthDiagnosticsClient(
            _settings(),
            transport=httpx.MockTransport(private_handler),
        ).get_diagnostics()
    assert private.value.code == "invalid_response"

    def inconsistent_handler(request: httpx.Request) -> httpx.Response:
        return _response(request, _payload(ready=False), 200)

    with pytest.raises(HealthDiagnosticsServiceError) as inconsistent:
        HealthDiagnosticsClient(
            _settings(),
            transport=httpx.MockTransport(inconsistent_handler),
        ).get_diagnostics()
    assert inconsistent.value.code == "invalid_response"
