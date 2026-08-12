from __future__ import annotations

import streamlit as st

from app.developer_access import require_developer_page

require_developer_page()

st.title("🛠️ Pliris Developer Console")
st.caption("Protected operational workspace")

st.success("Developer access boundary is active.")

st.markdown("### Phase 7 operational workspace")
st.write(
    "This protected shell brings together the source, feedback, monitoring, "
    "and API diagnostics capabilities delivered through Phase 7."
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Knowledge and feedback")
    st.markdown(
        "- Source inspection and document administration\n"
        "- Response and citation inspection\n"
        "- Feedback collection and analytics"
    )

with col2:
    st.markdown("#### Operations and quality")
    st.markdown(
        "- Monitoring events and storage\n"
        "- Usage, latency, quality, failure, and cost dashboards\n"
        "- API health and readiness diagnostics"
    )

st.info(
    "Phase 7 capabilities are available through the protected navigation. "
    "Use Health & Readiness for live dependency and safe configuration checks."
)
