import streamlit as st


def render_feedback_form(conversation_id: str, message_id: str):
    """Render a feedback form for a conversation."""
    st.markdown("#### 📝 Feedback")

    with st.form(key=f"feedback_{message_id}"):
        rating = st.slider(
            "Response Quality",
            min_value=1,
            max_value=5,
            value=3,
            help="Rate the quality of the response (1 = Poor, 5 = Excellent)",
        )

        helpful = st.radio(
            "Was this response helpful?", options=["Yes", "No", "Partially"], horizontal=True
        )

        categories = st.multiselect(
            "What aspects need improvement?",
            options=["Accuracy", "Completeness", "Clarity", "Relevance", "Citations", "Other"],
        )

        comments = st.text_area(
            "Additional Comments",
            placeholder="Please provide any additional feedback...",
            height=100,
        )

        submitted = st.form_submit_button("Submit Feedback")

        if submitted:
            feedback_data = {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "rating": rating,
                "helpful": helpful,
                "categories": categories,
                "comments": comments,
            }
            return feedback_data

    return None


def render_feedback_summary(feedback_stats: dict):
    """Render a summary of feedback statistics."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Feedback", feedback_stats.get("total", 0))

    with col2:
        avg_rating = feedback_stats.get("avg_rating", 0)
        st.metric("Avg Rating", f"{avg_rating:.1f}/5.0")

    with col3:
        helpful_pct = feedback_stats.get("helpful_percentage", 0)
        st.metric("Helpful %", f"{helpful_pct:.1f}%")

    with col4:
        st.metric("Response Rate", f"{feedback_stats.get('response_rate', 0):.1f}%")

    if feedback_stats.get("categories"):
        st.markdown("#### Common Issues")
        for category, count in feedback_stats["categories"].items():
            st.markdown(f"- **{category}**: {count}")
