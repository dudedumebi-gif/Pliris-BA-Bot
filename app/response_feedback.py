from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ResponseFeedbackTarget:
    """One persisted assistant response that may receive feedback."""

    conversation_id: str
    assistant_message_id: str
    has_citations: bool


def response_feedback_target(message: dict[str, Any]) -> ResponseFeedbackTarget | None:
    """Return a safe feedback target only for a successfully persisted answer."""

    if message.get("role") != "assistant":
        return None

    conversation_id = message.get("conversation_id")
    metadata = message.get("metadata")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return None
    if not isinstance(metadata, dict):
        return None

    persistence = metadata.get("persistence")
    if not isinstance(persistence, dict) or persistence.get("status") != "completed":
        return None

    assistant_message_id = persistence.get("assistant_message_id")
    try:
        normalized_message_id = str(UUID(str(assistant_message_id)))
    except (TypeError, ValueError, AttributeError):
        return None

    citations = message.get("citations")
    return ResponseFeedbackTarget(
        conversation_id=conversation_id.strip(),
        assistant_message_id=normalized_message_id,
        has_citations=isinstance(citations, list) and bool(citations),
    )


def feedback_state_key(assistant_message_id: str) -> str:
    """Return the isolated Streamlit state key for one assistant response."""

    return f"pliris_feedback_{assistant_message_id}"
