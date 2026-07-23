from __future__ import annotations

import pytest

from app import ui_config
from app.ui_config import UIConfigurationError, UIMode, load_ui_settings


def test_ui_settings_default_to_public_local_mode() -> None:
    settings = load_ui_settings({})

    assert settings.app_env == "development"
    assert settings.api_url == "http://localhost:8000"
    assert settings.api_timeout_seconds == 90
    assert settings.ui_mode is UIMode.PUBLIC
    assert settings.guest_ui_shared_secret is None
    assert settings.developer_ui_access_key is None


def test_ui_settings_normalize_hosted_configuration() -> None:
    settings = load_ui_settings(
        {
            "APP_ENV": "production",
            "API_URL": "https://api.example.test/",
            "API_TIMEOUT_SECONDS": "45",
            "PLIRIS_UI_MODE": "developer",
            "GUEST_UI_SHARED_SECRET": " ui-secret ",
            "DEVELOPER_UI_ACCESS_KEY": " developer-secret ",
        }
    )

    assert settings.api_url == "https://api.example.test"
    assert settings.api_timeout_seconds == 45
    assert settings.ui_mode is UIMode.DEVELOPER
    assert settings.guest_ui_shared_secret == "ui-secret"
    assert settings.developer_ui_access_key == "developer-secret"


def test_ui_settings_load_local_dotenv_with_process_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "APP_ENV=development\n"
        "API_URL=http://from-file:8000\n"
        "PLIRIS_UI_MODE=developer\n"
        "DEVELOPER_UI_ACCESS_KEY=local-developer-key\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(ui_config, "ENV_FILE", env_file)
    monkeypatch.setattr(
        ui_config.os,
        "environ",
        {"API_URL": "https://process-override.example.test"},
    )

    settings = load_ui_settings()

    assert settings.api_url == "https://process-override.example.test"
    assert settings.ui_mode is UIMode.DEVELOPER
    assert settings.developer_ui_access_key == "local-developer-key"


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        (
            {"PLIRIS_UI_MODE": "admin"},
            "PLIRIS_UI_MODE must be either",
        ),
        (
            {"API_URL": "localhost:8000"},
            "API_URL must be an absolute",
        ),
        (
            {
                "PLIRIS_UI_MODE": "developer",
            },
            "DEVELOPER_UI_ACCESS_KEY is required",
        ),
        (
            {
                "APP_ENV": "production",
            },
            "GUEST_UI_SHARED_SECRET is required",
        ),
    ],
)
def test_ui_settings_reject_invalid_configuration(
    environ: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(UIConfigurationError, match=message):
        load_ui_settings(environ)
