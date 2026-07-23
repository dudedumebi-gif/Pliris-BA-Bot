from pathlib import Path


def test_streamlit_uses_repository_root_entrypoint() -> None:
    assert Path("streamlit_app.py").is_file()
    assert not Path("app/Home.py").exists()


def test_automatic_page_directory_contains_only_public_chat() -> None:
    public_pages = sorted(path.name for path in Path("app/pages").glob("*.py"))

    assert public_pages == ["1_Chat.py"]


def test_developer_pages_are_outside_public_page_directory() -> None:
    expected = {
        "0_Developer.py",
        "2_Sources.py",
        "3_Feedback.py",
        "4_Monitoring.py",
    }
    actual = {path.name for path in Path("app/developer_pages").glob("*.py")}

    assert expected <= actual
