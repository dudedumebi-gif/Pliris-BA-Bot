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
    assert [page.title for page in manifest["Developer"]] == ["Developer Console"]
    assert manifest["Developer"][0].path == ("app/developer_pages/0_Developer.py")
    assert [page.title for page in manifest["Workspace"]] == ["Chat"]
