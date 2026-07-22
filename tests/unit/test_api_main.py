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
