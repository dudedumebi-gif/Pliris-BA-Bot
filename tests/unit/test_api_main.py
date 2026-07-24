from api.main import app


def test_production_app_registers_public_chat_route() -> None:
    paths = app.openapi()["paths"]

    assert "/api/chat/" in paths
    assert "post" in paths["/api/chat/"]
    assert "/api/chat/stream" in paths


def test_production_app_keeps_health_and_root_routes() -> None:
    paths = app.openapi()["paths"]

    assert "/" in paths
    assert any(path.startswith("/health") for path in paths)


def test_production_app_registers_protected_source_routes() -> None:
    paths = app.openapi()["paths"]
    assert "/api/sources/" in paths
    assert "/api/sources/stats" in paths
    assert "/api/sources/{source_id}" in paths
    assert "/api/sources/{source_id}/chunks" in paths
