from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.developer_access import get_expected_developer_key, require_developer_access
from api.routes.feedback import get_feedback_repository, router


class FakeRepository:
    def __init__(self) -> None:
        self.fail = False
        self.calls: list[dict[str, object]] = []

    async def get_stats(self) -> dict[str, object]:
        if self.fail:
            raise RuntimeError("private database detail")
        return {
            "total_feedback": 1,
            "helpful_feedback": 1,
            "unhelpful_feedback": 0,
            "commented_feedback": 1,
            "citation_ratings": 1,
            "citation_helpful": 1,
            "scope_ratings": 1,
            "scope_correct": 1,
            "latest_feedback_at": datetime(2026, 8, 5, tzinfo=UTC),
        }

    async def list_feedback(self, **kwargs: object) -> tuple[list[dict[str, object]], int]:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("private database detail")
        return [
            {
                "id": uuid4(),
                "assistant_message_id": uuid4(),
                "rating": 1,
                "citation_helpful": True,
                "scope_decision_correct": True,
                "comment": "Useful.",
                "user_message": "Question",
                "assistant_message": "Answer",
                "scope_status": "in_scope",
                "scope_confidence": 0.95,
                "citations": [],
                "model_name": "gpt-5-mini",
                "input_tokens": 10,
                "output_tokens": 20,
                "latency_ms": 30,
                "created_at": datetime(2026, 8, 5, tzinfo=UTC),
            }
        ], 1


def _client(*, bypass_access: bool = True) -> tuple[TestClient, FakeRepository]:
    app = FastAPI()
    app.include_router(router, prefix="/api/feedback")
    repository = FakeRepository()
    app.dependency_overrides[get_feedback_repository] = lambda: repository
    if bypass_access:
        app.dependency_overrides[require_developer_access] = lambda: None
    else:
        app.dependency_overrides[get_expected_developer_key] = lambda: "developer-secret"
    return TestClient(app, raise_server_exceptions=False), repository


def test_developer_feedback_routes_return_stats_and_filtered_items() -> None:
    client, repository = _client()

    stats = client.get("/api/feedback/stats")
    listing = client.get(
        "/api/feedback/",
        params={
            "limit": 25,
            "offset": 0,
            "rating": 1,
            "citation_helpful": True,
            "scope_decision_correct": True,
        },
    )
    invalid_rating = client.get("/api/feedback/", params={"rating": 0})

    assert stats.status_code == 200
    assert stats.json()["helpful_feedback"] == 1
    assert listing.status_code == 200
    assert invalid_rating.status_code == 422
    assert listing.json()["total"] == 1
    assert "conversation_id" not in listing.text
    assert "client_session_id" not in listing.text
    assert repository.calls == [
        {
            "limit": 25,
            "offset": 0,
            "rating": 1,
            "citation_helpful": True,
            "scope_decision_correct": True,
        }
    ]


def test_developer_feedback_routes_require_developer_key() -> None:
    client, _ = _client(bypass_access=False)

    missing = client.get("/api/feedback/stats")
    accepted = client.get(
        "/api/feedback/stats",
        headers={"X-Pliris-Developer-Key": "developer-secret"},
    )

    assert missing.status_code == 401
    assert accepted.status_code == 200


def test_developer_feedback_routes_hide_repository_errors() -> None:
    client, repository = _client()
    repository.fail = True

    stats = client.get("/api/feedback/stats")
    listing = client.get("/api/feedback/")

    assert stats.status_code == 500
    assert listing.status_code == 500
    assert "private database detail" not in stats.text
    assert "private database detail" not in listing.text
