from __future__ import annotations

import streamlit as st

from app.ui_config import UIMode, load_ui_settings


def require_developer_page() -> None:
    """Stop a developer page unless the protected session is active."""

    settings = load_ui_settings()
    authenticated = bool(st.session_state.get("developer_authenticated", False))

    if settings.ui_mode is UIMode.DEVELOPER and authenticated:
        return

    st.error("Developer access is required.")
    st.stop()
