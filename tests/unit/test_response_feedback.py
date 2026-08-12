from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from uuid import uuid4

from app.components.chat_message import copy_action_html
from app.response_feedback import feedback_state_key, response_feedback_target


def _message(*, assistant_message_id: str | None = None) -> dict:
    return {
        "role": "assistant",
        "conversation_id": "conversation-token",
        "assistant_message_id": assistant_message_id or str(uuid4()),
        "citations": [{"citation_id": "S1"}],
        "metadata": {"persistence": {"status": "failed"}},
    }


def test_response_feedback_target_uses_response_identity() -> None:
    assistant_message_id = str(uuid4())

    target = response_feedback_target(_message(assistant_message_id=assistant_message_id))

    assert target is not None
    assert target.conversation_id == "conversation-token"
    assert target.assistant_message_id == assistant_message_id
    assert target.has_citations is True


def test_response_feedback_target_does_not_depend_on_persistence_status() -> None:
    message = _message()

    for status in ("completed", "failed", "disabled"):
        message["metadata"]["persistence"]["status"] = status
        assert response_feedback_target(message) is not None


def test_response_feedback_target_rejects_missing_or_invalid_identity() -> None:
    message = _message()
    del message["assistant_message_id"]
    assert response_feedback_target(message) is None
    assert response_feedback_target(_message(assistant_message_id="not-a-uuid")) is None
    assert response_feedback_target({"role": "user"}) is None


def test_feedback_state_key_is_response_isolated() -> None:
    first = str(uuid4())
    second = str(uuid4())

    assert feedback_state_key(first) == f"pliris_feedback_{first}"
    assert feedback_state_key(first) != feedback_state_key(second)


def test_chat_page_renders_feedback_for_history_and_new_reply() -> None:
    source = Path("app/pages/1_Chat.py").read_text(encoding="utf-8")
    chat_component = Path("app/components/chat_message.py").read_text(encoding="utf-8")
    feedback_component = Path("app/components/response_feedback.py").read_text(encoding="utf-8")

    assert "FeedbackClient(settings)" in source
    assert source.count("render_response_feedback(") == 2
    assert "pliris_guest_session_id" in source
    assert "copy_key" in source
    assert 'label="Copy request"' in chat_component
    assert 'label="Copy response"' in feedback_component
    assert "copy, positive, negative" in feedback_component


def test_copy_action_html_encodes_untrusted_message_and_reports_success() -> None:
    message = '"><script>alert("unsafe")</script> café'

    rendered = copy_action_html(
        message,
        key="user-message-1",
        label="Copy request",
    )

    assert message not in rendered
    assert b64encode(message.encode("utf-8")).decode("ascii") in rendered
    assert 'aria-label="Copy request"' in rendered
    assert 'class="pliris-copy-text">Copy</span>' in rendered
    assert "color: var(--text-color, #fafafa);" in rendered
    assert "width: auto;" in rendered
    assert "navigator.clipboard.writeText(message)" in rendered
    assert 'document.execCommand("copy")' in rendered
    assert 'status.textContent = "Copied"' in rendered
