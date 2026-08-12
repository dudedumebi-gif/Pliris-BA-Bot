from __future__ import annotations

import pandas as pd
import streamlit as st

from app.health_view import (
    check_label,
    configuration_rows,
    format_checked_at,
    format_latency,
    status_label,
)
from app.services.health_client import (
    HealthDiagnosticsClient,
    HealthDiagnosticsServiceError,
)
from app.ui_config import load_ui_settings

settings = load_ui_settings()
client = HealthDiagnosticsClient(settings)

st.title("🩺 API Health & Readiness")
st.caption("Protected, read-only service and dependency diagnostics")

refresh_col, spacer = st.columns([1, 5])
with refresh_col:
    if st.button("Refresh", use_container_width=True):
        st.rerun()

try:
    diagnostics = client.get_diagnostics()
except HealthDiagnosticsServiceError as exc:
    st.error(exc.user_message)
    st.stop()

if diagnostics["status"] == "ready":
    st.success("The API and required dependencies are ready.")
else:
    st.warning("The API is live, but one or more required dependencies are unavailable.")

st.caption(f"Checked {format_checked_at(diagnostics['checked_at'])}")

check_columns = st.columns(len(diagnostics["checks"]))
for column, check in zip(check_columns, diagnostics["checks"], strict=True):
    with column:
        st.metric(
            check_label(check["name"]),
            status_label(check["status"]),
            format_latency(check["latency_ms"]),
            delta_color="off",
        )

st.subheader("Non-secret runtime configuration")
frame = pd.DataFrame(configuration_rows(diagnostics["configuration"]))
st.dataframe(frame, hide_index=True, use_container_width=True)

st.info(
    "This page never displays credentials, connection strings, exception text, "
    "prompts, responses, user identities, session identifiers, conversation "
    "identifiers, or message identifiers."
)
