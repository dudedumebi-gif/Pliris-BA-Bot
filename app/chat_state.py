from __future__ import annotations

from typing import Any


def discard_failed_user_turn(
    messages: list[dict[str, Any]],
    prompt: str,
) -> bool:
    """Remove the pending user turn after a failed API request."""

    if not messages:
        return False

    last_message = messages[-1]
    if last_message.get("role") == "user" and last_message.get("content") == prompt:
        messages.pop()
        return True

    return False
