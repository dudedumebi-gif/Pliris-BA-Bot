from __future__ import annotations

import streamlit as st

from app.navigation import PageSpec, navigation_manifest
from app.ui_auth import verify_developer_access
from app.ui_config import UIConfigurationError, UIMode, load_ui_settings

st.set_page_config(
    page_title="Pliris BA Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _streamlit_page(spec: PageSpec) -> st.Page:
    return st.Page(
        spec.path,
        title=spec.title,
        icon=spec.icon,
        default=spec.default,
    )


def _render_developer_login(expected_key: str | None) -> None:
    st.title("🛠️ Pliris Developer Access")
    st.write(
        "This protected interface contains operational and diagnostic "
        "capabilities intended only for the Pliris development team."
    )

    with st.form("developer-login", clear_on_submit=True):
        candidate = st.text_input(
            "Developer access code",
            type="password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Unlock developer interface")

    if submitted:
        if verify_developer_access(candidate, expected_key):
            st.session_state["developer_authenticated"] = True
            st.rerun()
        st.error("The developer access code was not accepted.")

    st.stop()


try:
    settings = load_ui_settings()
except UIConfigurationError:
    st.error(
        "The Pliris interface is not configured correctly. Please contact the application owner."
    )
    st.stop()

if settings.ui_mode is UIMode.DEVELOPER:
    authenticated = bool(st.session_state.get("developer_authenticated", False))

    if not authenticated:
        login_page = st.Page(
            lambda: _render_developer_login(settings.developer_ui_access_key),
            title="Developer Access",
            icon="🔐",
            default=True,
        )
        st.navigation([login_page], position="hidden").run()
        st.stop()

    with st.sidebar:
        st.caption("Protected developer interface")
        if st.button(
            "Lock developer interface",
            use_container_width=True,
        ):
            st.session_state["developer_authenticated"] = False
            st.rerun()

manifest = navigation_manifest(settings.ui_mode)

if isinstance(manifest, list):
    pages = [_streamlit_page(spec) for spec in manifest]
    current_page = st.navigation(pages, position="hidden")
else:
    pages = {
        section: [_streamlit_page(spec) for spec in specs] for section, specs in manifest.items()
    }
    current_page = st.navigation(pages, position="sidebar", expanded=True)

current_page.run()
