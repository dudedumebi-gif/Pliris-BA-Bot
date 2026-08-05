from __future__ import annotations

from datetime import datetime
from typing import Any


def format_percentage(numerator: Any, denominator: Any) -> str:
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        return "—"
    return f"{(numerator / denominator) * 100:.1f}%"


def format_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "Not recorded"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "Not recorded"
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def feedback_excerpt(value: Any, *, limit: int = 140) -> str:
    if not isinstance(value, str):
        return "No response text"
    normalized = " ".join(value.split())
    if not normalized:
        return "No response text"
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 1)].rstrip() + "…"


def feedback_label(item: dict[str, Any]) -> str:
    sentiment = "Helpful" if item.get("rating") == 1 else "Not helpful"
    return f"{sentiment} · {feedback_excerpt(item.get('assistant_message'))}"


def boolean_label(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Not rated"
