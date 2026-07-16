import streamlit as st


def render_citation_card(citation: dict, index: int):
    """Render a single citation card."""
    with st.expander(
        f"Citation {index + 1}: {citation.get('title', 'Unknown Document')}", expanded=False
    ):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**Source:** {citation.get('source', 'Unknown')}")
            st.markdown(f"**Page:** {citation.get('page', 'N/A')}")
            st.markdown(f"**Relevance Score:** {citation.get('score', 0):.2f}")

        with col2:
            if citation.get("score", 0) > 0.8:
                st.success("High")
            elif citation.get("score", 0) > 0.5:
                st.warning("Medium")
            else:
                st.error("Low")

        st.markdown("---")
        st.markdown("**Text Snippet:**")
        st.markdown(f"> {citation.get('text', '')[:500]}...")

        if citation.get("metadata"):
            st.markdown("**Metadata:**")
            st.json(citation["metadata"])


def render_citations_list(citations: list[dict], max_display: int = 5):
    """Render a list of citations."""
    if not citations:
        st.info("No citations available for this response.")
        return

    st.markdown(f"#### 📚 {len(citations)} Citations Found")

    display_citations = citations[:max_display]
    for i, citation in enumerate(display_citations):
        render_citation_card(citation, i)

    if len(citations) > max_display:
        st.info(f"Showing {max_display} of {len(citations)} citations.")


def render_source_summary(sources: list[dict]):
    """Render a summary of sources used."""
    if not sources:
        return

    source_counts = {}
    for source in sources:
        source_name = source.get("source", "Unknown")
        source_counts[source_name] = source_counts.get(source_name, 0) + 1

    st.markdown("#### 📊 Source Distribution")
    for source, count in source_counts.items():
        st.markdown(f"- **{source}**: {count} citation(s)")
