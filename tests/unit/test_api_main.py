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
    assert "/api/sources/stage" in paths
    assert "post" in paths["/api/sources/stage"]


def test_production_app_registers_public_feedback_route() -> None:
    paths = app.openapi()["paths"]

    assert "/api/feedback/" in paths
    assert "post" in paths["/api/feedback/"]


def test_production_app_registers_protected_feedback_inspection_routes() -> None:
    paths = app.openapi()["paths"]

    assert "get" in paths["/api/feedback/"]
    assert "/api/feedback/stats" in paths
    assert "get" in paths["/api/feedback/stats"]


def test_production_app_registers_protected_monitoring_event_route() -> None:
    paths = app.openapi()["paths"]

    assert "/api/monitoring/events" in paths
    assert "get" in paths["/api/monitoring/events"]


def test_production_app_registers_protected_monitoring_dashboard_route() -> None:
    paths = app.openapi()["paths"]

    assert "/api/monitoring/dashboard" in paths
    assert "get" in paths["/api/monitoring/dashboard"]
