from __future__ import annotations

from datetime import UTC, datetime

WINDOW_HOURS = {
    "Last 24 hours": 24,
    "Last 7 days": 168,
    "Last 30 days": 720,
}


def window_hours(label: str) -> int:
    """Translate one controlled dashboard label into the API window."""

    try:
        return WINDOW_HOURS[label]
    except KeyError as exc:
        raise ValueError("Unknown monitoring time range.") from exc


def format_count(value: int) -> str:
    """Format a non-negative aggregate count."""

    return f"{max(0, value):,}"


def format_latency(value: float | int | None) -> str:
    """Format milliseconds without inventing a value for an empty sample."""

    if value is None:
        return "—"
    if value < 1000:
        return f"{value:.0f} ms"
    if value < 60_000:
        return f"{value / 1000:.2f} s"
    return f"{value / 60_000:.1f} min"


def format_percentage(numerator: int, denominator: int) -> str:
    """Format a bounded rate and preserve no-sample state."""

    if denominator <= 0:
        return "—"
    return f"{min(100.0, max(0.0, numerator / denominator * 100)):.1f}%"


def format_generated_at(value: str) -> str:
    """Render an API timestamp in a stable UTC form."""

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "at an unknown time"
    return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
