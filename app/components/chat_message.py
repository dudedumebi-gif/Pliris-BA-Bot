import streamlit as st


def render_user_message(message: str, timestamp: str | None = None):
    """Render a user chat message."""
    with st.chat_message("user"):
        st.write(message)
        if timestamp:
            st.caption(f"{timestamp}")


def render_assistant_message(
    message: str,
    citations: list[dict] | None = None,
    timestamp: str | None = None,
    confidence: float | None = None,
):
    """Render an assistant chat message with optional citations."""
    with st.chat_message("assistant"):
        st.write(message)

        if citations:
            st.markdown("#### 📚 Citations")
            for i, citation in enumerate(citations, 1):
                with st.expander(f"Citation {i}: {citation.get('title', 'Unknown')}"):
                    st.markdown(f"**Source:** {citation.get('source', 'Unknown')}")
                    st.markdown(f"**Relevance:** {citation.get('score', 0):.2f}")
                    st.markdown(f"**Snippet:** {citation.get('text', '')[:200]}...")

        if confidence is not None:
            st.caption(f"Confidence: {confidence:.1%}")

        if timestamp:
            st.caption(f"{timestamp}")


def render_system_message(message: str):
    """Render a system message."""
    with st.chat_message("system"):
        st.info(message)


def render_feedback_buttons(message_id: str):
    """Render feedback buttons for a message."""
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👍 Helpful", key=f"up_{message_id}"):
            return "positive"
    with col2:
        if st.button("👎 Not Helpful", key=f"down_{message_id}"):
            return "negative"
    return None
