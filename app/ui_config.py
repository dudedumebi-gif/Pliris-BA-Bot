from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class UIConfigurationError(ValueError):
    """Raised when the Streamlit deployment configuration is invalid."""


class UIMode(StrEnum):
    """Supported Streamlit interface modes."""

    PUBLIC = "public"
    DEVELOPER = "developer"


@dataclass(frozen=True)
class UISettings:
    """Server-side settings used by the Streamlit process."""

    app_env: str
    api_url: str
    api_timeout_seconds: float
    ui_mode: UIMode
    guest_ui_shared_secret: str | None
    developer_ui_access_key: str | None


def load_ui_settings(
    environ: Mapping[str, str] | None = None,
) -> UISettings:
    """Load and validate Streamlit-only configuration."""

    values = os.environ if environ is None else environ

    app_env = values.get("APP_ENV", "development").strip().lower()
    api_url = values.get("API_URL", "http://localhost:8000").strip().rstrip("/")
    raw_mode = values.get("PLIRIS_UI_MODE", UIMode.PUBLIC.value).strip().lower()
    guest_secret = _optional_secret(values.get("GUEST_UI_SHARED_SECRET"))
    developer_key = _optional_secret(values.get("DEVELOPER_UI_ACCESS_KEY"))

    try:
        ui_mode = UIMode(raw_mode)
    except ValueError as exc:
        raise UIConfigurationError(
            "PLIRIS_UI_MODE must be either 'public' or 'developer'."
        ) from exc

    parsed_url = urlparse(api_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise UIConfigurationError("API_URL must be an absolute HTTP or HTTPS URL.")

    raw_timeout = values.get("API_TIMEOUT_SECONDS", "90").strip()
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise UIConfigurationError("API_TIMEOUT_SECONDS must be a number.") from exc

    if not 1 <= timeout <= 300:
        raise UIConfigurationError("API_TIMEOUT_SECONDS must be between 1 and 300.")

    if app_env == "production" and guest_secret is None:
        raise UIConfigurationError("GUEST_UI_SHARED_SECRET is required when APP_ENV=production.")

    if ui_mode is UIMode.DEVELOPER and developer_key is None:
        raise UIConfigurationError("DEVELOPER_UI_ACCESS_KEY is required in developer mode.")

    return UISettings(
        app_env=app_env,
        api_url=api_url,
        api_timeout_seconds=timeout,
        ui_mode=ui_mode,
        guest_ui_shared_secret=guest_secret,
        developer_ui_access_key=developer_key,
    )


def _optional_secret(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None
