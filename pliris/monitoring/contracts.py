from __future__ import annotations

import json
import math
import re
from typing import Any, Literal

MonitoringSeverity = Literal["debug", "info", "warning", "error", "critical"]

ALLOWED_SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})
MAX_PROPERTIES_BYTES = 8_192
MAX_PROPERTY_DEPTH = 4
MAX_PROPERTY_ITEMS = 100
MAX_PROPERTY_STRING_LENGTH = 512

_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SENSITIVE_PROPERTY_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "client_session_id",
        "content",
        "email",
        "error_message",
        "message",
        "original_query",
        "password",
        "prompt",
        "query",
        "rewritten_query",
        "secret",
        "session_id",
        "stack_trace",
        "token",
        "user_id",
    }
)
_SENSITIVE_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_email",
    "_password",
    "_secret",
    "_session_id",
    "_token",
    "_user_id",
)


def validate_event_type(value: str) -> str:
    """Return one normalized bounded event type."""

    if not isinstance(value, str):
        raise ValueError("event_type must be a string")
    normalized = value.strip().lower()
    if not _EVENT_TYPE_PATTERN.fullmatch(normalized):
        raise ValueError(
            "event_type must start with a letter and contain only lowercase "
            "letters, numbers, dots, underscores, or hyphens"
        )
    return normalized


def validate_severity(value: str) -> MonitoringSeverity:
    """Return one supported monitoring severity."""

    if not isinstance(value, str):
        raise ValueError("severity must be a string")
    normalized = value.strip().lower()
    if normalized not in ALLOWED_SEVERITIES:
        raise ValueError("severity is not supported")
    return normalized  # type: ignore[return-value]


def sanitize_event_properties(value: dict[str, Any] | None) -> dict[str, Any]:
    """Validate privacy-safe, bounded JSON properties before storage."""

    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("properties must be an object")

    sanitized = _sanitize_mapping(value, depth=0, reject_sensitive=True)
    encoded = json.dumps(
        sanitized,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > MAX_PROPERTIES_BYTES:
        raise ValueError("properties exceed the storage limit")
    return sanitized


def redact_event_properties(value: object) -> dict[str, Any]:
    """Return a bounded developer-safe projection of stored properties."""

    if not isinstance(value, dict):
        return {}
    return _sanitize_mapping(value, depth=0, reject_sensitive=False)


def _sanitize_mapping(
    value: dict[object, object],
    *,
    depth: int,
    reject_sensitive: bool,
) -> dict[str, Any]:
    if depth > MAX_PROPERTY_DEPTH:
        raise ValueError("properties exceed the nesting limit")
    if len(value) > MAX_PROPERTY_ITEMS:
        raise ValueError("properties contain too many fields")

    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            raise ValueError("property keys must be strings")
        key = raw_key.strip()
        if not key or len(key) > 64:
            raise ValueError("property keys must contain 1 to 64 characters")
        normalized_key = key.lower()
        if _is_sensitive_key(normalized_key):
            if reject_sensitive:
                raise ValueError(f"property '{key}' is not allowed")
            continue
        result[key] = _sanitize_value(
            raw_value,
            depth=depth + 1,
            reject_sensitive=reject_sensitive,
        )
    return result


def _sanitize_value(value: object, *, depth: int, reject_sensitive: bool) -> Any:
    if depth > MAX_PROPERTY_DEPTH:
        raise ValueError("properties exceed the nesting limit")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("numeric properties must be finite")
        return value
    if isinstance(value, str):
        if len(value) > MAX_PROPERTY_STRING_LENGTH:
            raise ValueError("property strings exceed the length limit")
        return value
    if isinstance(value, dict):
        return _sanitize_mapping(
            value,
            depth=depth,
            reject_sensitive=reject_sensitive,
        )
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_PROPERTY_ITEMS:
            raise ValueError("property lists contain too many items")
        return [
            _sanitize_value(
                item,
                depth=depth + 1,
                reject_sensitive=reject_sensitive,
            )
            for item in value
        ]
    raise ValueError("properties must contain JSON-compatible values")


def _is_sensitive_key(value: str) -> bool:
    return value in _SENSITIVE_PROPERTY_KEYS or value.endswith(_SENSITIVE_SUFFIXES)
