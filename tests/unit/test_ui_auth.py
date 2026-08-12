from app.ui_auth import verify_developer_access


def test_developer_access_accepts_exact_secret() -> None:
    assert verify_developer_access("correct", "correct") is True


def test_developer_access_rejects_wrong_or_missing_secret() -> None:
    assert verify_developer_access("wrong", "correct") is False
    assert verify_developer_access("anything", None) is False
