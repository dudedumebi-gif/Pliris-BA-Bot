from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.developer_access import (
    DEVELOPER_KEY_HEADER,
    get_expected_developer_key,
    require_developer_access,
)


def _client(expected_key: str | None) -> TestClient:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_developer_access)])
    def protected() -> dict[str, str]:
        return {"status": "ok"}

    app.dependency_overrides[get_expected_developer_key] = lambda: expected_key
    return TestClient(app)


def test_developer_api_rejects_missing_configuration() -> None:
    assert _client(None).get("/protected").status_code == 503


def test_developer_api_rejects_missing_or_incorrect_key() -> None:
    client = _client("expected-secret")
    assert client.get("/protected").status_code == 401
    assert (
        client.get(
            "/protected",
            headers={DEVELOPER_KEY_HEADER: "wrong-secret"},
        ).status_code
        == 401
    )


def test_developer_api_accepts_matching_key() -> None:
    response = _client("expected-secret").get(
        "/protected",
        headers={DEVELOPER_KEY_HEADER: "expected-secret"},
    )
    assert response.status_code == 200
