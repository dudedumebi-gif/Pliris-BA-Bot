import httpx
import streamlit as st

st.set_page_config(page_title="Sources - Pliris BA Bot", page_icon="📚", layout="wide")

st.markdown("# 📚 Document Sources")
st.markdown("View and manage the documents in your knowledge base.")

# Tabs for different views
tab1, tab2, tab3 = st.tabs(["All Documents", "Upload New", "Document Details"])

with tab1:
    st.markdown("### Indexed Documents")

    # Fetch documents from API
    try:
        with httpx.Client() as client:
            response = client.get("http://localhost:8000/api/sources", timeout=30.0)
            response.raise_for_status()
            documents = response.json()

        if documents:
            # Display documents in a table
            for doc in documents:
                with st.expander(f"📄 {doc.get('title', 'Untitled')}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown(f"**Source:** {doc.get('source', 'Unknown')}")
                        st.markdown(f"**Type:** {doc.get('type', 'Unknown')}")

                    with col2:
                        st.markdown(f"**Chunks:** {doc.get('chunk_count', 0)}")
                        st.markdown(f"**Uploaded:** {doc.get('uploaded_at', 'Unknown')}")

                    with col3:
                        st.markdown(f"**Status:** {doc.get('status', 'Unknown')}")
                        if doc.get("status") == "indexed":
                            st.success("Indexed")
                        else:
                            st.warning("Processing")
        else:
            st.info("No documents found in the knowledge base.")

    except httpx.HTTPError as e:
        st.error(f"Error fetching documents: {e}")

with tab2:
    st.markdown("### Upload New Document")

    uploaded_file = st.file_uploader(
        "Choose a file", type=["pdf", "docx", "txt"], help="Supported formats: PDF, DOCX, TXT"
    )

    if uploaded_file:
        col1, col2 = st.columns(2)

        with col1:
            title = st.text_input("Document Title", value=uploaded_file.name)
            source = st.text_input("Source/Author", placeholder="e.g., Annual Report 2024")

        with col2:
            doc_type = st.selectbox(
                "Document Type", ["Report", "Policy", "Procedure", "Contract", "Other"]
            )
            tags = st.text_input("Tags (comma-separated)", placeholder="e.g., finance, q1, 2024")

        if st.button("Upload Document"):
            try:
                files = {"file": (uploaded_file.name, uploaded_file, uploaded_file.type)}
                data = {"title": title, "source": source, "type": doc_type, "tags": tags}

                with httpx.Client() as client:
                    response = client.post(
                        "http://localhost:8000/api/sources/upload",
                        files=files,
                        data=data,
                        timeout=300.0,
                    )
                    response.raise_for_status()

                st.success("Document uploaded successfully! It will be processed shortly.")
                st.rerun()

            except httpx.HTTPError as e:
                st.error(f"Error uploading document: {e}")

with tab3:
    st.markdown("### Document Statistics")

    try:
        with httpx.Client() as client:
            response = client.get("http://localhost:8000/api/sources/stats", timeout=30.0)
            response.raise_for_status()
            stats = response.json()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Documents", stats.get("total_documents", 0))

        with col2:
            st.metric("Total Chunks", stats.get("total_chunks", 0))

        with col3:
            st.metric("Indexed Documents", stats.get("indexed_documents", 0))

        with col4:
            st.metric("Pending Processing", stats.get("pending_documents", 0))

    except httpx.HTTPError as e:
        st.error(f"Error fetching statistics: {e}")
