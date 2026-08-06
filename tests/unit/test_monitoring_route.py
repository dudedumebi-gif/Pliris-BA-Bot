from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.developer_access import get_expected_developer_key, require_developer_access
from api.routes.monitoring import (
    get_metrics_collector,
    get_monitoring_repository,
    router,
)


class FakeRepository:
    def __init__(self) -> None:
        self.fail = False
        self.calls: list[dict[str, object]] = []

    async def list_events(self, **kwargs: object) -> tuple[list[dict[str, object]], int]:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("private database detail")
        return [
            {
                "id": uuid4(),
                "event_type": "chat.request.completed",
                "severity": "info",
                "properties": {"latency_ms": 250},
                "created_at": datetime(2026, 8, 5, tzinfo=UTC),
            }
        ], 1

    async def get_dashboard(self, *, since_hours: int) -> dict[str, object]:
        self.calls.append({"dashboard_since_hours": since_hours})
        if self.fail:
            raise RuntimeError("private database detail")
        return {
            "generated_at": datetime(2026, 8, 5, tzinfo=UTC),
            "since_hours": since_hours,
            "bucket": "hour" if since_hours <= 48 else "day",
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
            "response_timeline": [{"timestamp": datetime(2026, 8, 5, tzinfo=UTC), "count": 8}],
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


def _client(*, bypass_access: bool = True) -> tuple[TestClient, FakeRepository]:
    app = FastAPI()
    app.include_router(router, prefix="/api/monitoring")
    repository = FakeRepository()
    app.dependency_overrides[get_monitoring_repository] = lambda: repository
    app.dependency_overrides[get_metrics_collector] = lambda: repository
    if bypass_access:
        app.dependency_overrides[require_developer_access] = lambda: None
    else:
        app.dependency_overrides[get_expected_developer_key] = lambda: "developer-secret"
    return TestClient(app, raise_server_exceptions=False), repository


def test_monitoring_route_returns_filtered_events() -> None:
    client, repository = _client()

    response = client.get(
        "/api/monitoring/events",
        params={
            "limit": 25,
            "offset": 0,
            "since_hours": 168,
            "event_type": "chat.request.completed",
            "severity": "info",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert "conversation_id" not in response.text
    assert "message_id" not in response.text
    assert repository.calls == [
        {
            "limit": 25,
            "offset": 0,
            "since_hours": 168,
            "event_type": "chat.request.completed",
            "severity": "info",
        }
    ]


def test_monitoring_route_requires_developer_key() -> None:
    client, _ = _client(bypass_access=False)

    missing = client.get("/api/monitoring/events")
    accepted = client.get(
        "/api/monitoring/events",
        headers={"X-Pliris-Developer-Key": "developer-secret"},
    )

    assert missing.status_code == 401
    assert accepted.status_code == 200


def test_monitoring_route_rejects_invalid_filters_and_hides_errors() -> None:
    client, repository = _client()

    invalid_type = client.get(
        "/api/monitoring/events",
        params={"event_type": "Invalid Event"},
    )
    repository.fail = True
    failed = client.get("/api/monitoring/events")

    assert invalid_type.status_code == 422
    assert failed.status_code == 500
    assert "private database detail" not in failed.text


def test_monitoring_dashboard_returns_protected_real_aggregates() -> None:
    client, repository = _client()

    response = client.get(
        "/api/monitoring/dashboard",
        params={"since_hours": 168},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["since_hours"] == 168
    assert payload["bucket"] == "day"
    assert payload["summary"]["total_responses"] == 8
    assert payload["summary"]["input_tokens"] == 1200
    assert repository.calls == [{"dashboard_since_hours": 168}]
    assert "client_session_id" not in response.text
    assert "conversation_id" not in response.text
    assert "content" not in response.text


def test_monitoring_dashboard_requires_access_and_hides_failures() -> None:
    protected_client, _ = _client(bypass_access=False)
    assert protected_client.get("/api/monitoring/dashboard").status_code == 401

    client, repository = _client()
    repository.fail = True
    failed = client.get("/api/monitoring/dashboard")

    assert failed.status_code == 500
    assert "private database detail" not in failed.text
