import httpx
import streamlit as st
from app.components.feedback import render_feedback_form, render_feedback_summary
from app.components.chat_message import render_feedback_buttons


st.set_page_config(page_title="Feedback - Pliris BA Bot", page_icon="👍", layout="wide")

st.markdown("# 👍 Feedback")
st.markdown("Provide feedback on AI responses to help improve the system.")

# Tabs
tab1, tab2 = st.tabs(["Submit Feedback", "Feedback Analytics"])

with tab1:
    st.markdown("### Recent Conversations")

    # Fetch recent conversations
    try:
        with httpx.Client() as client:
            response = client.get("http://localhost:8000/api/feedback/conversations", timeout=30.0)
            response.raise_for_status()
            conversations = response.json()

        if conversations:
            selected_conversation = st.selectbox(
                "Select a conversation to provide feedback",
                options=conversations,
                format_func=lambda x: (
                    f"Conversation {x.get('id', 'Unknown')} - {x.get('created_at', 'Unknown')}"
                ),
            )

            if selected_conversation:
                st.markdown("---")

                # Display conversation messages
                for msg in selected_conversation.get("messages", []):
                    if msg["role"] == "user":
                        st.chat_message("user").write(msg["content"])
                    else:
                        st.chat_message("assistant").write(msg["content"])

                        # Add feedback button for assistant messages
                        feedback = render_feedback_buttons(msg.get("id", ""))

                        if feedback:
                            # Show detailed feedback form
                            st.markdown("---")
                            feedback_data = render_feedback_form(
                                selected_conversation["id"], msg["id"]
                            )

                            if feedback_data:
                                try:
                                    with httpx.Client() as client:
                                        response = client.post(
                                            "http://localhost:8000/api/feedback",
                                            json=feedback_data,
                                            timeout=30.0,
                                        )
                                        response.raise_for_status()

                                    st.success("Thank you for your feedback!")
                                    st.rerun()

                                except httpx.HTTPError as e:
                                    st.error(f"Error submitting feedback: {e}")
        else:
            st.info("No recent conversations found.")

    except httpx.HTTPError as e:
        st.error(f"Error fetching conversations: {e}")

with tab2:
    st.markdown("### Feedback Analytics")

    try:
        with httpx.Client() as client:
            response = client.get("http://localhost:8000/api/feedback/analytics", timeout=30.0)
            response.raise_for_status()
            analytics = response.json()

        render_feedback_summary(analytics)

        st.markdown("---")
        st.markdown("### Recent Feedback")

        if analytics.get("recent_feedback"):
            for feedback in analytics["recent_feedback"]:
                with st.expander(f"Feedback from {feedback.get('created_at', 'Unknown')}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"**Rating:** {feedback.get('rating', 'N/A')}/5")
                        st.markdown(f"**Helpful:** {feedback.get('helpful', 'N/A')}")

                    with col2:
                        st.markdown(f"**Categories:** {', '.join(feedback.get('categories', []))}")

                    if feedback.get("comments"):
                        st.markdown(f"**Comments:** {feedback['comments']}")
        else:
            st.info("No feedback data available yet.")

    except httpx.HTTPError as e:
        st.error(f"Error fetching analytics: {e}")
