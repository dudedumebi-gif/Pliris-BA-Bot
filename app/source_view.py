from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any


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
