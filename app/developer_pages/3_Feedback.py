from __future__ import annotations

import streamlit as st

from app.feedback_view import (
    boolean_label,
    feedback_label,
    format_percentage,
    format_timestamp,
)
from app.services.developer_feedback_client import (
    DeveloperFeedbackClient,
    DeveloperFeedbackServiceError,
)
from app.ui_config import load_ui_settings

settings = load_ui_settings()
client = DeveloperFeedbackClient(settings)

st.title("💬 Response Feedback")
st.caption("Protected, read-only inspection of response-level quality signals")

rating_col, citation_col, scope_col, refresh_col = st.columns([2, 2, 2, 1])
with rating_col:
    rating_filter = st.selectbox("Rating", ["All", "Helpful", "Not helpful"])
with citation_col:
    citation_filter = st.selectbox("Citation helpful", ["All", "Yes", "No"])
with scope_col:
    scope_filter = st.selectbox("Scope decision correct", ["All", "Yes", "No"])
with refresh_col:
    st.write("")
    st.write("")
    if st.button("Refresh", use_container_width=True):
        st.rerun()

rating = {"Helpful": 1, "Not helpful": -1}.get(rating_filter)
citation_helpful = {"Yes": True, "No": False}.get(citation_filter)
scope_correct = {"Yes": True, "No": False}.get(scope_filter)

try:
    stats = client.get_stats()
    first_page = client.list_feedback(
        limit=25,
        offset=0,
        rating=rating,
        citation_helpful=citation_helpful,
        scope_decision_correct=scope_correct,
    )
except DeveloperFeedbackServiceError as exc:
    st.error(exc.user_message)
    st.stop()

metrics = st.columns(5)
metrics[0].metric("Responses rated", stats["total_feedback"])
metrics[1].metric(
    "Helpful rate",
    format_percentage(stats["helpful_feedback"], stats["total_feedback"]),
)
metrics[2].metric(
    "Citation helpful",
    format_percentage(stats["citation_helpful"], stats["citation_ratings"]),
)
metrics[3].metric(
    "Scope correct",
    format_percentage(stats["scope_correct"], stats["scope_ratings"]),
)
metrics[4].metric("Comments", stats["commented_feedback"])
st.caption(f"Latest feedback: {format_timestamp(stats.get('latest_feedback_at'))}")

if first_page.total == 0:
    st.info("No response feedback matches the current filters.")
    st.stop()

page_size = 25
page_total = max(1, (first_page.total + page_size - 1) // page_size)
selected_page = st.number_input(
    "Feedback page",
    min_value=1,
    max_value=page_total,
    value=1,
    step=1,
)

if selected_page == 1:
    page = first_page
else:
    try:
        page = client.list_feedback(
            limit=page_size,
            offset=(selected_page - 1) * page_size,
            rating=rating,
            citation_helpful=citation_helpful,
            scope_decision_correct=scope_correct,
        )
    except DeveloperFeedbackServiceError as exc:
        st.error(exc.user_message)
        st.stop()

st.caption(f"Showing {len(page.items)} of {page.total} feedback records.")
for item in page.items:
    with st.expander(feedback_label(item)):
        st.markdown("**User question**")
        st.write(item.get("user_message") or "Not recorded")
        st.markdown("**Assistant response**")
        st.write(item["assistant_message"])

        details = st.columns(3)
        details[0].markdown(
            f"**Citation helpful:** {boolean_label(item.get('citation_helpful'))}"
        )
        details[1].markdown(
            f"**Scope correct:** {boolean_label(item.get('scope_decision_correct'))}"
        )
        details[2].markdown(
            f"**Submitted:** {format_timestamp(item.get('created_at'))}"
        )

        comment = item.get("comment")
        if isinstance(comment, str) and comment.strip():
            st.markdown("**Comment**")
            st.write(comment)

        citations = item.get("citations")
        if isinstance(citations, list) and citations:
            st.markdown(f"**Citations ({len(citations)})**")
            st.json(citations)
        else:
            st.caption("No citations were persisted for this response.")

        st.caption(
            f"Scope: {item.get('scope_status') or 'not recorded'} · "
            f"Model: {item.get('model_name') or 'not recorded'} · "
            f"Latency: {item.get('latency_ms') if item.get('latency_ms') is not None else '—'} ms"
        )

st.info(
    "This workspace is read-only. It does not expose guest-session identifiers or "
    "provide feedback deletion or modification controls."
)
