from __future__ import annotations

import pandas as pd
import streamlit as st

from app.monitoring_view import (
    format_count,
    format_generated_at,
    format_latency,
    format_percentage,
    window_hours,
)
from app.services.monitoring_client import (
    MonitoringDashboardClient,
    MonitoringDashboardServiceError,
)
from app.ui_config import load_ui_settings

settings = load_ui_settings()
client = MonitoringDashboardClient(settings)

st.title("📊 System Monitoring")
st.caption("Protected, aggregate-only operational and response-quality signals")

window_col, refresh_col = st.columns([4, 1])
with window_col:
    selected_window = st.selectbox(
        "Time range",
        ["Last 24 hours", "Last 7 days", "Last 30 days"],
        index=0,
    )
with refresh_col:
    st.write("")
    st.write("")
    if st.button("Refresh", use_container_width=True):
        st.rerun()

try:
    dashboard = client.get_dashboard(since_hours=window_hours(selected_window))
except MonitoringDashboardServiceError as exc:
    st.error(exc.user_message)
    st.stop()

summary = dashboard["summary"]
metrics = st.columns(5)
metrics[0].metric("Responses", format_count(summary["total_responses"]))
metrics[1].metric(
    "Active conversations",
    format_count(summary["active_conversations"]),
)
metrics[2].metric("Average latency", format_latency(summary["avg_latency_ms"]))
metrics[3].metric("P95 latency", format_latency(summary["p95_latency_ms"]))
metrics[4].metric(
    "Helpful feedback",
    format_percentage(summary["helpful_feedback"], summary["feedback_records"]),
)

st.caption(
    f"Generated {format_generated_at(dashboard['generated_at'])} · "
    f"{summary['latency_samples']:,} latency samples · "
    f"{summary['token_samples']:,} token samples"
)

volume_col, scope_col = st.columns(2)
with volume_col:
    st.subheader("Response volume")
    timeline = dashboard["response_timeline"]
    if timeline:
        frame = pd.DataFrame(timeline)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        st.line_chart(frame.set_index("timestamp")["count"])
    else:
        st.info("No responses were recorded in this time range.")

with scope_col:
    st.subheader("Scope decisions")
    scope = dashboard["scope_breakdown"]
    if scope:
        frame = pd.DataFrame(scope).set_index("name")
        st.bar_chart(frame["count"])
    else:
        st.info("No scope decisions were recorded in this time range.")

latency_col, model_col = st.columns(2)
with latency_col:
    st.subheader("Latency distribution")
    latency = dashboard["latency_distribution"]
    if latency:
        frame = pd.DataFrame(latency).set_index("label")
        st.bar_chart(frame["count"])
    else:
        st.info("No latency samples were recorded in this time range.")

with model_col:
    st.subheader("Model and token usage")
    model_usage = dashboard["model_usage"]
    if model_usage:
        frame = pd.DataFrame(model_usage).rename(
            columns={
                "name": "Model",
                "count": "Responses",
                "input_tokens": "Input tokens",
                "output_tokens": "Output tokens",
            }
        )
        st.dataframe(frame, hide_index=True, use_container_width=True)
    else:
        st.info("No model usage was recorded in this time range.")

quality_col, failure_col = st.columns(2)
with quality_col:
    st.subheader("Quality and safety")
    quality = pd.DataFrame(
        [
            {"Signal": "Feedback records", "Count": summary["feedback_records"]},
            {"Signal": "Helpful", "Count": summary["helpful_feedback"]},
            {"Signal": "Not helpful", "Count": summary["unhelpful_feedback"]},
            {"Signal": "With comments", "Count": summary["commented_feedback"]},
            {
                "Signal": "Prompt injections blocked",
                "Count": summary["prompt_injection_blocks"],
            },
        ]
    )
    st.dataframe(quality, hide_index=True, use_container_width=True)

with failure_col:
    st.subheader("Failure breakdown")
    failures = dashboard["failure_breakdown"]
    if failures:
        frame = pd.DataFrame(failures).set_index("name")
        st.bar_chart(frame["count"])
    else:
        st.success("No failures were recorded in this time range.")

st.caption(
    f"Input tokens: {summary['input_tokens']:,} · "
    f"Output tokens: {summary['output_tokens']:,} · "
    f"Request failures: {summary['request_failures']:,} · "
    f"Feedback submissions: {summary['feedback_submissions']:,}"
)

st.info(
    "This dashboard is read-only and aggregate-only. It does not expose prompts, "
    "responses, guest-session identifiers, conversation identifiers, or message identifiers."
)
