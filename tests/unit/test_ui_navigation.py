from app.navigation import navigation_manifest
from app.ui_config import UIMode


def test_public_navigation_exposes_only_chat() -> None:
    manifest = navigation_manifest(UIMode.PUBLIC)

    assert isinstance(manifest, list)
    assert [page.title for page in manifest] == ["Chat"]
    assert manifest[0].path == "app/pages/1_Chat.py"
    assert manifest[0].default is True


def test_developer_navigation_exposes_protected_shell_and_chat() -> None:
    manifest = navigation_manifest(UIMode.DEVELOPER)

    assert isinstance(manifest, dict)
    assert list(manifest) == ["Developer", "Workspace"]
    assert [page.title for page in manifest["Developer"]] == [
        "Developer Console",
        "Sources",
        "Response Feedback",
        "Monitoring",
        "Health & Readiness",
    ]
    assert manifest["Developer"][0].path == ("app/developer_pages/0_Developer.py")
    assert manifest["Developer"][1].path == ("app/developer_pages/2_Sources.py")
    assert manifest["Developer"][2].path == ("app/developer_pages/3_Feedback.py")
    assert manifest["Developer"][3].path == ("app/developer_pages/4_Monitoring.py")
    assert manifest["Developer"][4].path == ("app/developer_pages/5_Health.py")
    assert [page.title for page in manifest["Workspace"]] == ["Chat"]


def test_sources_page_relies_on_centralized_developer_boundary() -> None:
    from pathlib import Path

    source = Path("app/developer_pages/2_Sources.py").read_text(encoding="utf-8")

    assert "require_developer_page" not in source
    assert "app.developer_guard" not in source


def test_sources_page_limits_staging_to_controlled_manifest() -> None:
    from pathlib import Path

    source = Path("app/developer_pages/2_Sources.py").read_text(encoding="utf-8")

    assert "STAGING_ACCEPTANCE_MANIFEST_ID" in source
    assert "staging_filename_for_manifest" in source
    assert "client.stage_pdf" in source
    assert "No ingestion was started." in source
    assert 'st.selectbox("Manifest source"' not in source


def test_monitoring_page_uses_protected_aggregate_client() -> None:
    from pathlib import Path

    source = Path("app/developer_pages/4_Monitoring.py").read_text(encoding="utf-8")

    assert "MonitoringDashboardClient" in source
    assert "/api/monitoring" not in source
    assert "recent_events" not in source
    assert "st.json" not in source
    assert "aggregate-only" in source


def test_health_page_uses_protected_bounded_client() -> None:
    from pathlib import Path

    source = Path("app/developer_pages/5_Health.py").read_text(encoding="utf-8")

    assert "HealthDiagnosticsClient" in source
    assert "/health/" not in source
    assert "st.json" not in source
    assert "credentials" in source
    assert "session identifiers" in source
