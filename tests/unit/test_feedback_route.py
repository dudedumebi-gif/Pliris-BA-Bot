from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.conversation_tokens import (
    ConversationTokenManager,
    get_conversation_token_manager,
)
from api.guest_access import get_guest_user
from api.routes.feedback import get_feedback_repository, router
from pliris.database.repositories.feedback import FeedbackTargetNotFoundError


class FakeRepository:
    def __init__(self, assistant_message_id: UUID) -> None:
        self.assistant_message_id = assistant_message_id
        self.calls: list[dict] = []
        self.mode = "success"

    async def upsert(self, **values):
        self.calls.append(values)
        if self.mode == "not_found":
            raise FeedbackTargetNotFoundError
        if self.mode == "error":
            raise RuntimeError("private database detail")
        return {
            "id": uuid4(),
            "assistant_message_id": self.assistant_message_id,
            "rating": values["rating"],
            "citation_helpful": values["citation_helpful"],
            "scope_decision_correct": values["scope_decision_correct"],
            "comment": values["comment"],
            "created_at": datetime.now(UTC),
        }


def _client():
    session_id = uuid4()
    tokens = ConversationTokenManager("test-secret")
    conversation_id = tokens.issue(str(session_id))
    assistant_message_id = uuid4()
    repository = FakeRepository(assistant_message_id)

    app = FastAPI()
    app.include_router(router, prefix="/api/feedback")
    app.dependency_overrides[get_guest_user] = lambda: {
        "id": f"guest-{session_id.hex}",
        "name": "Guest User",
        "session_id": str(session_id),
    }
    app.dependency_overrides[get_conversation_token_manager] = lambda: tokens
    app.dependency_overrides[get_feedback_repository] = lambda: repository

    return (
        TestClient(app),
        repository,
        tokens,
        session_id,
        conversation_id,
        assistant_message_id,
    )


def _payload(conversation_id: str, assistant_message_id: UUID) -> dict:
    return {
        "conversation_id": conversation_id,
        "assistant_message_id": str(assistant_message_id),
        "rating": 1,
        "citation_helpful": True,
        "scope_decision_correct": None,
        "comment": "  Useful answer.  ",
    }


def test_feedback_route_upserts_session_owned_response() -> None:
    client, repository, _, _, conversation_id, assistant_message_id = _client()

    response = client.post(
        "/api/feedback/",
        json=_payload(conversation_id, assistant_message_id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    assert response.json()["assistant_message_id"] == str(assistant_message_id)
    assert repository.calls[0]["client_session_id"] == conversation_id
    assert repository.calls[0]["comment"] == "Useful answer."


def test_feedback_route_rejects_invalid_or_foreign_conversation_token() -> None:
    client, repository, tokens, _, _, assistant_message_id = _client()

    malformed = client.post(
        "/api/feedback/",
        json=_payload("not-a-token", assistant_message_id),
    )
    foreign_token = tokens.issue(str(uuid4()))
    foreign = client.post(
        "/api/feedback/",
        json=_payload(foreign_token, assistant_message_id),
    )

    assert malformed.status_code == 400
    assert foreign.status_code == 403
    assert repository.calls == []


def test_feedback_route_hides_unowned_message_and_database_errors() -> None:
    client, repository, _, _, conversation_id, assistant_message_id = _client()

    repository.mode = "not_found"
    missing = client.post(
        "/api/feedback/",
        json=_payload(conversation_id, assistant_message_id),
    )
    repository.mode = "error"
    failed = client.post(
        "/api/feedback/",
        json=_payload(conversation_id, assistant_message_id),
    )

    assert missing.status_code == 404
    assert missing.json() == {"detail": "Feedback target was not found."}
    assert failed.status_code == 500
    assert failed.json() == {"detail": "Failed to submit feedback."}
    assert "private database detail" not in failed.text


def test_feedback_route_validates_rating_comment_and_extra_fields() -> None:
    client, repository, _, _, conversation_id, assistant_message_id = _client()
    payload = _payload(conversation_id, assistant_message_id)

    invalid_rating = client.post(
        "/api/feedback/",
        json={**payload, "rating": 0},
    )
    long_comment = client.post(
        "/api/feedback/",
        json={**payload, "comment": "x" * 1001},
    )
    extra_field = client.post(
        "/api/feedback/",
        json={**payload, "user_id": "spoofed"},
    )

    assert invalid_rating.status_code == 422
    assert long_comment.status_code == 422
    assert extra_field.status_code == 422
    assert repository.calls == []
