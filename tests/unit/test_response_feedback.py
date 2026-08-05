from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.response_feedback import feedback_state_key, response_feedback_target


def _message(*, status: str = "completed", assistant_message_id: str | None = None) -> dict:
    return {
        "role": "assistant",
        "conversation_id": "conversation-token",
        "citations": [{"citation_id": "S1"}],
        "metadata": {
            "persistence": {
                "status": status,
                "assistant_message_id": assistant_message_id or str(uuid4()),
            }
        },
    }


def test_response_feedback_target_requires_completed_persistence() -> None:
    assistant_message_id = str(uuid4())

    target = response_feedback_target(
        _message(assistant_message_id=assistant_message_id)
    )

    assert target is not None
    assert target.conversation_id == "conversation-token"
    assert target.assistant_message_id == assistant_message_id
    assert target.has_citations is True


def test_response_feedback_target_rejects_unpersisted_or_invalid_messages() -> None:
    assert response_feedback_target(_message(status="failed")) is None
    assert response_feedback_target(_message(status="disabled")) is None
    assert response_feedback_target(_message(assistant_message_id="not-a-uuid")) is None
    assert response_feedback_target({"role": "user"}) is None


def test_feedback_state_key_is_response_isolated() -> None:
    first = str(uuid4())
    second = str(uuid4())

    assert feedback_state_key(first) == f"pliris_feedback_{first}"
    assert feedback_state_key(first) != feedback_state_key(second)


def test_chat_page_renders_feedback_for_history_and_new_reply() -> None:
    source = Path("app/pages/1_Chat.py").read_text(encoding="utf-8")

    assert "FeedbackClient(settings)" in source
    assert source.count("render_response_feedback(") == 2
    assert "pliris_guest_session_id" in source
