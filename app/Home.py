import streamlit as st
from streamlit_option_menu import option_menu

st.set_page_config(
    page_title="Pliris BA Bot", page_icon="🤖", layout="wide", initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar navigation
with st.sidebar:
    st.title("🤖 Pliris BA Bot")
    st.markdown("---")

    selected = option_menu(
        menu_title="Navigation",
        options=["Home", "Chat", "Sources", "Feedback", "Monitoring"],
        icons=["house", "chat-dots", "database", "hand-thumbs-up", "graph-up"],
        menu_icon="cast",
        default_index=0,
    )

    st.markdown("---")
    st.markdown("### System Status")
    st.success("✓ API Connected")
    st.success("✓ Database Connected")
    st.success("✓ LLM Service Ready")

# Main content
if selected == "Home":
    st.markdown('<h1 class="main-header">Welcome to Pliris BA Bot</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Your AI-powered Business Analyst Assistant</p>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Documents Indexed", "1,234", "+15")
        st.markdown("#### 📊 Document Sources")
        st.markdown("- PDF Reports")
        st.markdown("- Word Documents")
        st.markdown("- Web Pages")

    with col2:
        st.metric("Queries Processed", "5,678", "+23")
        st.markdown("#### 💬 Chat Features")
        st.markdown("- Semantic Search")
        st.markdown("- Citations")
        st.markdown("- Context Awareness")

    with col3:
        st.metric("Avg Response Time", "2.3s", "-0.5")
        st.markdown("#### 🔒 Guardrails")
        st.markdown("- Scope Classification")
        st.markdown("- Prompt Injection")
        st.markdown("- Evidence Checking")

    st.markdown("---")

    st.markdown("### Getting Started")
    st.info(
        "Navigate to the **Chat** page to start asking questions about your business documents."
    )
