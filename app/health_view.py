from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

CHECK_LABELS = {
    "api_process": "API process",
    "supabase_data_api": "Supabase Data API",
    "postgres": "PostgreSQL",
}

CONFIGURATION_LABELS = {
    "app_name": "Application",
    "app_env": "Environment",
    "chat_model": "Chat model",
    "embedding_model": "Embedding model",
    "embedding_dimensions": "Embedding dimensions",
    "storage_bucket": "Storage bucket",
    "monitoring_enabled": "Monitoring enabled",
    "feedback_enabled": "Feedback enabled",
}


def check_label(name: str) -> str:
    """Return a controlled display label for one known health check."""

    try:
        return CHECK_LABELS[name]
    except KeyError as exc:
        raise ValueError("Unknown health check.") from exc


def status_label(value: str) -> str:
    """Translate one controlled status without inventing a healthy state."""

    if value == "healthy":
        return "Healthy"
    if value == "unavailable":
        return "Unavailable"
    raise ValueError("Unknown health status.")


def format_latency(value: float | int) -> str:
    """Format bounded probe latency."""

    if value < 1:
        return "<1 ms"
    if value < 1000:
        return f"{value:.0f} ms"
    return f"{value / 1000:.2f} s"


def format_checked_at(value: str) -> str:
    """Render a diagnostics timestamp in stable UTC form."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "at an unknown time"
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def configuration_rows(configuration: dict[str, Any]) -> list[dict[str, Any]]:
    """Return safe configuration in a stable display order."""

    return [
        {"Setting": label, "Value": configuration[key]}
        for key, label in CONFIGURATION_LABELS.items()
    ]
