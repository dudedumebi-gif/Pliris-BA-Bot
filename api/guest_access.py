from __future__ import annotations

import hmac
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status

from pliris.config.settings import get_settings

SESSION_HEADER = "X-Pliris-Session-ID"
UI_KEY_HEADER = "X-Pliris-UI-Key"


@dataclass(frozen=True)
class GuestAccessPolicy:
    """Server-side controls for anonymous public chat access."""

    shared_secret: str | None
    request_window_seconds: int
    requests_per_window: int
    max_requests_per_session: int
    session_retention_seconds: int


class InMemoryGuestRateLimiter:
    """Conservative single-process limiter for public-review deployments."""

    def __init__(self, policy: GuestAccessPolicy) -> None:
        self._policy = policy
        self._events: dict[str, deque[float]] = {}
        self._totals: dict[str, int] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def enforce(self, session_id: str, *, now: float | None = None) -> None:
        """Raise HTTP 429 when a session exceeds configured limits."""

        current = time.monotonic() if now is None else now

        with self._lock:
            self._prune_stale(current)
            events = self._events.setdefault(session_id, deque())
            cutoff = current - self._policy.request_window_seconds

            while events and events[0] <= cutoff:
                events.popleft()

            session_total = self._totals.get(session_id, 0)
            self._last_seen[session_id] = current

            if session_total >= self._policy.max_requests_per_session:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "This guest session has reached its request limit. "
                        "Please start a new session later."
                    ),
                )

            if len(events) >= self._policy.requests_per_window:
                retry_after = max(
                    1,
                    math.ceil(events[0] + self._policy.request_window_seconds - current),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please wait before trying again.",
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(current)
            self._totals[session_id] = session_total + 1

    def _prune_stale(self, current: float) -> None:
        stale_before = current - self._policy.session_retention_seconds
        stale_sessions = [
            session_id
            for session_id, last_seen in self._last_seen.items()
            if last_seen <= stale_before
        ]

        for session_id in stale_sessions:
            self._events.pop(session_id, None)
            self._totals.pop(session_id, None)
            self._last_seen.pop(session_id, None)


def get_guest_access_policy() -> GuestAccessPolicy:
    """Build the current validated guest-access policy."""

    settings = get_settings()
    secret = (
        settings.guest_ui_shared_secret.get_secret_value()
        if settings.guest_ui_shared_secret is not None
        else None
    )
    return GuestAccessPolicy(
        shared_secret=secret,
        request_window_seconds=settings.guest_request_window_seconds,
        requests_per_window=settings.guest_requests_per_window,
        max_requests_per_session=settings.guest_max_requests_per_session,
        session_retention_seconds=settings.guest_session_retention_seconds,
    )


@lru_cache(maxsize=1)
def get_guest_rate_limiter() -> InMemoryGuestRateLimiter:
    """Return the process-local guest limiter."""

    return InMemoryGuestRateLimiter(get_guest_access_policy())


async def get_guest_user(
    request: Request,
    policy: GuestAccessPolicy = Depends(get_guest_access_policy),
    limiter: InMemoryGuestRateLimiter = Depends(get_guest_rate_limiter),
) -> dict[str, str]:
    """Validate the server-rendered UI request and derive an anonymous user."""

    _verify_ui_key(request, policy)
    session_id = _validated_session_id(request)
    limiter.enforce(session_id)

    parsed = UUID(session_id)
    return {
        "id": f"guest-{parsed.hex}",
        "name": "Guest User",
        "session_id": str(parsed),
    }


def _verify_ui_key(request: Request, policy: GuestAccessPolicy) -> None:
    expected = policy.shared_secret
    if expected is None:
        return

    provided = request.headers.get(UI_KEY_HEADER, "")
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public chat access is not authorized.",
        )


def _validated_session_id(request: Request) -> str:
    raw_value = request.headers.get(SESSION_HEADER, "").strip()
    if not raw_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing guest session identifier.",
        )

    try:
        parsed = UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid guest session identifier.",
        ) from exc

    return str(parsed)
