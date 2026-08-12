from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.developer_access import get_expected_developer_key
from api.routes.health import get_health_probes, router
from pliris.config.settings import get_settings


def _healthy() -> None:
    return None


def _unavailable() -> None:
    raise RuntimeError("private database failure")


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        app_name="Pliris BA Bot",
        app_env="test",
        openai_chat_model="gpt-test",
        openai_embedding_model="embedding-test",
        openai_embedding_dimensions=1536,
        supabase_storage_bucket="knowledge-base",
        enable_monitoring=True,
        enable_feedback=True,
    )


def _client(
    *,
    probes=(("supabase_data_api", _healthy), ("postgres", _healthy)),
    developer_key: str | None = "developer-secret",
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_health_probes] = lambda: probes
    app.dependency_overrides[get_expected_developer_key] = lambda: developer_key
    app.dependency_overrides[get_settings] = _settings
    return TestClient(app, raise_server_exceptions=False)


def test_public_liveness_is_minimal() -> None:
    response = _client().get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_public_readiness_is_minimal_when_ready() -> None:
    response = _client().get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert "postgres" not in response.text
    assert "supabase" not in response.text


def test_public_readiness_hides_dependency_and_exception_details() -> None:
    response = _client(probes=(("supabase_data_api", _healthy), ("postgres", _unavailable))).get(
        "/health/ready"
    )

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "postgres" not in response.text
    assert "private database failure" not in response.text


def test_protected_diagnostics_requires_developer_access() -> None:
    client = _client()

    assert client.get("/health/diagnostics").status_code == 401
    accepted = client.get(
        "/health/diagnostics",
        headers={"X-Pliris-Developer-Key": "developer-secret"},
    )
    assert accepted.status_code == 200


def test_protected_diagnostics_returns_safe_dependency_details() -> None:
    response = _client(probes=(("supabase_data_api", _healthy), ("postgres", _unavailable))).get(
        "/health/diagnostics",
        headers={"X-Pliris-Developer-Key": "developer-secret"},
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert [check["name"] for check in payload["checks"]] == [
        "api_process",
        "supabase_data_api",
        "postgres",
    ]
    assert payload["checks"][2]["status"] == "unavailable"
    assert payload["configuration"]["chat_model"] == "gpt-test"
    assert "private database failure" not in response.text
    assert "supabase_secret_key" not in response.text
    assert "supabase_db_url" not in response.text


def test_non_secret_config_is_protected_and_bounded() -> None:
    client = _client()

    assert client.get("/health/config").status_code == 401
    response = client.get(
        "/health/config",
        headers={"X-Pliris-Developer-Key": "developer-secret"},
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "app_name",
        "app_env",
        "chat_model",
        "embedding_model",
        "embedding_dimensions",
        "storage_bucket",
        "monitoring_enabled",
        "feedback_enabled",
    }
    assert "secret" not in response.text.lower()
    assert "postgresql://" not in response.text
