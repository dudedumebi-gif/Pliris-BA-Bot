from __future__ import annotations

import hmac


def verify_developer_access(
    candidate: str,
    expected: str | None,
) -> bool:
    """Compare the submitted developer access code in constant time."""

    if expected is None:
        return False
    return hmac.compare_digest(candidate, expected)
