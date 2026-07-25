from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any, Literal

PROTECTED_LIFECYCLE_MANIFEST_IDS = frozenset({"babok-v3"})
LIFECYCLE_ACCEPTANCE_MANIFEST_ID = "gao-agile-assessment-guide-2023"
LifecycleAction = Literal["archive", "restore"]


def format_count(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "0"
    return f"{max(number, 0):,}"


def format_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "Not available"
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return "Not available"
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def page_range_label(chunk: dict[str, Any]) -> str:
    start = chunk.get("page_start")
    end = chunk.get("page_end")
    if not isinstance(start, int):
        return "Page not recorded"
    if not isinstance(end, int) or end == start:
        return f"Page {start}"
    return f"Pages {start}-{end}"


def chunk_page_count(total: int, page_size: int) -> int:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    return max(1, ceil(max(total, 0) / page_size))


def source_option_label(source: dict[str, Any]) -> str:
    title = source.get("title")
    status = source.get("status")
    chunks = format_count(source.get("chunk_count"))
    safe_title = title.strip() if isinstance(title, str) and title.strip() else "Untitled source"
    safe_status = status.strip() if isinstance(status, str) and status.strip() else "unknown"
    return f"{safe_title} · {safe_status} · {chunks} chunks"


def lifecycle_action_for_source(source: dict[str, Any]) -> LifecycleAction | None:
    manifest_id = source.get("manifest_id")
    if manifest_id in PROTECTED_LIFECYCLE_MANIFEST_IDS:
        return None

    status = source.get("status")
    if status == "ready":
        return "archive"
    if status == "archived":
        return "restore"
    return None


def validate_lifecycle_input(
    *,
    reason: str,
    confirmation: str,
    manifest_id: Any,
) -> str | None:
    normalized_reason = reason.strip()
    if not 10 <= len(normalized_reason) <= 500:
        return "Provide a reason between 10 and 500 characters."
    if not isinstance(manifest_id, str) or not manifest_id:
        return "This source has no manifest ID and cannot be changed from the interface."
    if confirmation != manifest_id:
        return "Enter the exact, case-sensitive manifest ID shown above."
    return None


def lifecycle_event_label(event: dict[str, Any]) -> str:
    action = event.get("action")
    previous_status = event.get("previous_status")
    new_status = event.get("new_status")
    safe_action = action.title() if isinstance(action, str) else "Lifecycle event"
    safe_previous = previous_status if isinstance(previous_status, str) else "unknown"
    safe_new = new_status if isinstance(new_status, str) else "unknown"
    return (
        f"{safe_action} · {safe_previous} → {safe_new} · "
        f"{format_timestamp(event.get('created_at'))}"
    )
