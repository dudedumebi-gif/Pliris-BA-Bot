from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.guest_access import (
    GuestAccessPolicy,
    InMemoryGuestRateLimiter,
    get_guest_access_policy,
    get_guest_rate_limiter,
    get_guest_user,
)


def build_client(
    *,
    secret: str | None = "server-secret",
    requests_per_window: int = 2,
    max_requests_per_session: int = 3,
) -> TestClient:
    policy = GuestAccessPolicy(
        shared_secret=secret,
        request_window_seconds=60,
        requests_per_window=requests_per_window,
        max_requests_per_session=max_requests_per_session,
        session_retention_seconds=3600,
    )
    limiter = InMemoryGuestRateLimiter(policy)

    app = FastAPI()

    @app.get("/whoami")
    async def whoami(
        user: dict[str, str] = Depends(get_guest_user),
    ) -> dict[str, str]:
        return user

    app.dependency_overrides[get_guest_access_policy] = lambda: policy
    app.dependency_overrides[get_guest_rate_limiter] = lambda: limiter
    return TestClient(app)


def test_guest_access_requires_session_identifier() -> None:
    response = build_client().get(
        "/whoami",
        headers={"X-Pliris-UI-Key": "server-secret"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Missing guest session identifier."}


def test_guest_access_rejects_invalid_session_identifier() -> None:
    response = build_client().get(
        "/whoami",
        headers={
            "X-Pliris-UI-Key": "server-secret",
            "X-Pliris-Session-ID": "not-a-uuid",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid guest session identifier."}


def test_guest_access_rejects_invalid_ui_key() -> None:
    response = build_client().get(
        "/whoami",
        headers={
            "X-Pliris-UI-Key": "wrong-secret",
            "X-Pliris-Session-ID": str(uuid4()),
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Public chat access is not authorized."}


def test_guest_access_derives_isolated_anonymous_identity() -> None:
    session_id = uuid4()
    response = build_client().get(
        "/whoami",
        headers={
            "X-Pliris-UI-Key": "server-secret",
            "X-Pliris-Session-ID": str(session_id),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": f"guest-{session_id.hex}",
        "name": "Guest User",
        "session_id": str(session_id),
    }


def test_guest_access_enforces_rolling_window_limit() -> None:
    client = build_client(requests_per_window=2, max_requests_per_session=5)
    headers = {
        "X-Pliris-UI-Key": "server-secret",
        "X-Pliris-Session-ID": str(uuid4()),
    }

    assert client.get("/whoami", headers=headers).status_code == 200
    assert client.get("/whoami", headers=headers).status_code == 200

    response = client.get("/whoami", headers=headers)
    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests. Please wait before trying again."}
    assert response.headers["retry-after"] == "60"


def test_guest_access_allows_development_without_shared_secret() -> None:
    response = build_client(secret=None).get(
        "/whoami",
        headers={"X-Pliris-Session-ID": str(uuid4())},
    )

    assert response.status_code == 200
