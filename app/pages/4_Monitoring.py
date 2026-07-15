
import httpx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Monitoring - Pliris BA Bot", page_icon="📊", layout="wide")

st.markdown("# 📊 System Monitoring")
st.markdown("Real-time monitoring of system performance and usage metrics.")

# Time range selector
time_range = st.selectbox(
    "Time Range", ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"], index=0
)

# Fetch monitoring data
try:
    with httpx.Client() as client:
        response = client.get(
            f"http://localhost:8000/api/monitoring?range={time_range}", timeout=30.0
        )
        response.raise_for_status()
        monitoring_data = response.json()

    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Total Queries",
            monitoring_data.get("total_queries", 0),
            monitoring_data.get("queries_change", "0"),
        )

    with col2:
        st.metric(
            "Avg Response Time",
            f"{monitoring_data.get('avg_response_time', 0):.2f}s",
            f"{monitoring_data.get('response_time_change', 0):.2f}s",
        )

    with col3:
        st.metric(
            "Success Rate",
            f"{monitoring_data.get('success_rate', 0):.1f}%",
            f"{monitoring_data.get('success_rate_change', 0):.1f}%",
        )

    with col4:
        st.metric(
            "Avg Confidence",
            f"{monitoring_data.get('avg_confidence', 0):.1f}%",
            f"{monitoring_data.get('confidence_change', 0):.1f}%",
        )

    with col5:
        st.metric(
            "Active Users",
            monitoring_data.get("active_users", 0),
            monitoring_data.get("users_change", "0"),
        )

    st.markdown("---")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Query Volume Over Time")
        if monitoring_data.get("query_timeline"):
            df = pd.DataFrame(monitoring_data["query_timeline"])
            st.line_chart(df.set_index("timestamp")["count"])
        else:
            st.info("No data available")

    with col2:
        st.markdown("### Response Time Distribution")
        if monitoring_data.get("response_times"):
            df = pd.DataFrame(monitoring_data["response_times"])
            st.bar_chart(df["response_time"])
        else:
            st.info("No data available")

    st.markdown("---")

    # System health
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### System Health")
        health = monitoring_data.get("system_health", {})

        if health.get("api_status") == "healthy":
            st.success("✓ API Service")
        else:
            st.error("✗ API Service")

        if health.get("database_status") == "healthy":
            st.success("✓ Database")
        else:
            st.error("✗ Database")

        if health.get("llm_status") == "healthy":
            st.success("✓ LLM Service")
        else:
            st.error("✗ LLM Service")

        if health.get("embedding_status") == "healthy":
            st.success("✓ Embedding Service")
        else:
            st.error("✗ Embedding Service")

    with col2:
        st.markdown("### Resource Usage")
        resources = monitoring_data.get("resources", {})

        st.progress(resources.get("cpu_usage", 0) / 100)
        st.caption(f"CPU: {resources.get('cpu_usage', 0)}%")

        st.progress(resources.get("memory_usage", 0) / 100)
        st.caption(f"Memory: {resources.get('memory_usage', 0)}%")

        st.progress(resources.get("disk_usage", 0) / 100)
        st.caption(f"Disk: {resources.get('disk_usage', 0)}%")

    with col3:
        st.markdown("### Error Breakdown")
        errors = monitoring_data.get("errors", {})

        if errors:
            for error_type, count in errors.items():
                st.markdown(f"- **{error_type}**: {count}")
        else:
            st.success("No errors in selected time range")

    st.markdown("---")

    # Recent events
    st.markdown("### Recent Events")
    if monitoring_data.get("recent_events"):
        for event in monitoring_data["recent_events"]:
            with st.expander(
                f"{event.get('timestamp', 'Unknown')} - {event.get('type', 'Unknown')}"
            ):
                st.markdown(f"**Level:** {event.get('level', 'Unknown')}")
                st.markdown(f"**Message:** {event.get('message', 'Unknown')}")
                if event.get("metadata"):
                    st.json(event["metadata"])
    else:
        st.info("No recent events")

except httpx.HTTPError as e:
    st.error(f"Error fetching monitoring data: {e}")
except Exception as e:
    st.error(f"An error occurred: {e}")
