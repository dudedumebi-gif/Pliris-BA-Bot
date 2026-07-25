from __future__ import annotations

import json

import httpx
import pytest

from app.services.source_client import (
    DEVELOPER_KEY_HEADER,
    SourceClient,
    SourceServiceError,
)
from app.ui_config import UIMode, UISettings


def _settings(
    *,
    developer_key: str | None = "developer-secret",
) -> UISettings:
    return UISettings(
        app_env="development",
        api_url="https://api.example.test",
        api_timeout_seconds=30.0,
        ui_mode=UIMode.DEVELOPER,
        guest_ui_shared_secret=None,
        developer_ui_access_key=developer_key,
    )


def _json_response(
    request: httpx.Request,
    payload: object,
    *,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=request,
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )


def test_source_client_sends_developer_key_and_parses_list() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["key"] = request.headers.get(DEVELOPER_KEY_HEADER)
        return _json_response(
            request,
            {
                "items": [{"id": "source-1", "title": "BABOK"}],
                "total": 1,
                "limit": 25,
                "offset": 0,
            },
        )

    page = SourceClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).list_sources(
        query="BABOK",
        status="ready",
        limit=25,
        offset=0,
    )

    assert page.total == 1
    assert page.items[0]["title"] == "BABOK"
    assert observed["key"] == "developer-secret"
    assert observed["url"] == (
        "https://api.example.test/api/sources/?limit=25&offset=0&query=BABOK&status=ready"
    )


def test_source_client_parses_chunks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "document_id": "source-1",
                "items": [{"id": "chunk-1", "content": "text"}],
                "total": 1,
                "limit": 10,
                "offset": 0,
            },
        )

    page = SourceClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).get_chunks("source-1")

    assert page.document_id == "source-1"
    assert page.total == 1


def _lifecycle_event() -> dict[str, object]:
    return {
        "id": "event-1",
        "document_id": "source-1",
        "action": "archive",
        "actor": "developer-api",
        "reason": "Superseded for lifecycle acceptance testing.",
        "previous_status": "ready",
        "new_status": "archived",
        "metadata": {"manifest_id": "gao-agile-assessment-guide-2023"},
        "created_at": "2026-07-24T12:00:00+00:00",
    }


def test_source_client_parses_lifecycle_events() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        return _json_response(
            request,
            {
                "document_id": "source-1",
                "items": [_lifecycle_event()],
                "total": 1,
                "limit": 20,
                "offset": 0,
            },
        )

    page = SourceClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    ).get_events("source-1")

    assert page.total == 1
    assert page.items[0]["action"] == "archive"
    assert (
        observed["url"] == "https://api.example.test/api/sources/source-1/events?limit=20&offset=0"
    )


@pytest.mark.parametrize(
    ("method_name", "action"),
    [
        ("archive_source", "archive"),
        ("restore_source", "restore"),
    ],
)
def test_source_client_sends_guarded_lifecycle_request(
    method_name: str,
    action: str,
) -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["method"] = request.method
        observed["url"] = str(request.url)
        observed["body"] = json.loads(request.content)
        payload = _lifecycle_event()
        if action == "restore":
            payload |= {
                "action": "restore",
                "previous_status": "archived",
                "new_status": "ready",
            }
        return _json_response(request, payload)

    client = SourceClient(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    result = getattr(client, method_name)(
        "source-1",
        reason="Lifecycle acceptance test.",
        confirmation="gao-agile-assessment-guide-2023",
    )

    assert result["action"] == action
    assert observed == {
        "method": "POST",
        "url": f"https://api.example.test/api/sources/source-1/{action}",
        "body": {
            "reason": "Lifecycle acceptance test.",
            "confirmation": "gao-agile-assessment-guide-2023",
        },
    }


def test_source_client_rejects_missing_developer_configuration() -> None:
    with pytest.raises(SourceServiceError) as caught:
        SourceClient(_settings(developer_key=None)).get_stats()

    assert caught.value.code == "not_configured"


def test_source_client_returns_safe_authorization_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {"detail": "internal secret mismatch"},
            status_code=401,
        )

    with pytest.raises(SourceServiceError) as caught:
        SourceClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).get_stats()

    assert caught.value.code == "not_authorized"
    assert "internal secret mismatch" not in caught.value.user_message


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (400, "confirmation_mismatch"),
        (409, "lifecycle_conflict"),
        (422, "validation"),
        (500, "server_error"),
        (503, "unavailable"),
    ],
)
def test_source_client_translates_lifecycle_failures_safely(
    status_code: int,
    expected_code: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {"detail": "sensitive database and source details"},
            status_code=status_code,
        )

    with pytest.raises(SourceServiceError) as caught:
        SourceClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).archive_source(
            "source-1",
            reason="Lifecycle acceptance test.",
            confirmation="wrong-id",
        )

    assert caught.value.code == expected_code
    assert "sensitive database" not in caught.value.user_message


def test_source_client_translates_lifecycle_timeout_safely() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive network details", request=request)

    with pytest.raises(SourceServiceError) as caught:
        SourceClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).restore_source(
            "source-1",
            reason="Lifecycle acceptance test.",
            confirmation="gao-agile-assessment-guide-2023",
        )

    assert caught.value.code == "timeout"
    assert "sensitive network details" not in caught.value.user_message


def test_source_client_rejects_forbidden_response_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(
            request,
            {
                "id": "source-1",
                "storage_path": "private/path.pdf",
            },
        )

    with pytest.raises(SourceServiceError) as caught:
        SourceClient(
            _settings(),
            transport=httpx.MockTransport(handler),
        ).get_source("source-1")

    assert caught.value.code == "invalid_response"
