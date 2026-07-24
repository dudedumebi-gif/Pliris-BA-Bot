from __future__ import annotations

import streamlit as st

from app.services.source_client import SourceClient, SourceServiceError
from app.source_view import (
    chunk_page_count,
    format_count,
    format_timestamp,
    page_range_label,
    source_option_label,
)
from app.ui_config import load_ui_settings

settings = load_ui_settings()
client = SourceClient(settings)

st.title("📚 Knowledge-Base Sources")
st.caption("Protected read-only inspection of indexed documents and page-aware chunks.")

search_col, status_col, refresh_col = st.columns([3, 2, 1])
with search_col:
    query = st.text_input(
        "Search sources",
        placeholder="Title, author, filename, or manifest ID",
        max_chars=200,
    )
with status_col:
    selected_status = st.selectbox(
        "Status",
        ["All", "ready", "pending", "processing", "failed", "archived"],
    )
with refresh_col:
    st.write("")
    st.write("")
    if st.button("Refresh", use_container_width=True):
        st.rerun()

try:
    stats = client.get_stats()
    source_page = client.list_sources(
        query=query.strip() or None,
        status=None if selected_status == "All" else selected_status,
        limit=100,
        offset=0,
    )
except SourceServiceError as exc:
    st.error(exc.user_message)
    st.stop()

metrics = st.columns(5)
metrics[0].metric("Documents", format_count(stats.get("total_documents")))
metrics[1].metric("Ready", format_count(stats.get("ready_documents")))
metrics[2].metric("Chunks", format_count(stats.get("total_chunks")))
metrics[3].metric("Pages", format_count(stats.get("total_pages")))
metrics[4].metric("Tokens", format_count(stats.get("total_tokens")))
st.caption(f"Last successful ingestion: {format_timestamp(stats.get('last_ingested_at'))}")

if not source_page.items:
    st.info("No knowledge-base sources match the current filters.")
    st.stop()

source_by_id = {
    str(source["id"]): source for source in source_page.items if isinstance(source.get("id"), str)
}
if not source_by_id:
    st.error("The source service returned no usable source identifiers.")
    st.stop()

source_id = st.selectbox(
    "Inspect source",
    list(source_by_id),
    format_func=lambda value: source_option_label(source_by_id[value]),
)

try:
    detail = client.get_source(source_id)
except SourceServiceError as exc:
    st.error(exc.user_message)
    st.stop()

st.markdown("### Document details")
cols = st.columns(3)
with cols[0]:
    st.markdown(f"**Title:** {detail.get('title', 'Untitled')}")
    st.markdown(f"**Author:** {detail.get('author') or 'Not recorded'}")
    st.markdown(f"**Edition:** {detail.get('edition') or 'Not recorded'}")
    st.markdown(f"**Publication year:** {detail.get('publication_year') or 'Not recorded'}")
with cols[1]:
    st.markdown(f"**Manifest ID:** `{detail.get('manifest_id') or 'Not recorded'}`")
    st.markdown(f"**Source filename:** {detail.get('source_filename') or 'Not recorded'}")
    st.markdown(f"**Source type:** {detail.get('source_type', 'unknown')}")
    st.markdown(f"**Access:** {detail.get('access', 'private')}")
with cols[2]:
    st.markdown(f"**Status:** `{detail.get('status', 'unknown')}`")
    st.markdown(f"**Pages:** {format_count(detail.get('page_count'))}")
    st.markdown(f"**Chunks:** {format_count(detail.get('chunk_count'))}")
    st.markdown(f"**Indexed tokens:** {format_count(detail.get('total_tokens'))}")

if detail.get("has_ingestion_error"):
    st.warning(
        "This source has an ingestion failure recorded. "
        "Raw failure details are intentionally hidden."
    )

with st.expander("Integrity and ingestion metadata"):
    checksum = detail.get("checksum_sha256")
    st.markdown(
        f"**SHA-256:** `{checksum}`" if isinstance(checksum, str) else "**SHA-256:** Not recorded"
    )
    st.markdown(f"**Last ingested:** {format_timestamp(detail.get('last_ingested_at'))}")
    st.markdown(f"**MIME type:** {detail.get('mime_type', 'Not recorded')}")
    metadata = detail.get("metadata")
    if isinstance(metadata, dict) and metadata:
        st.json(metadata)
    else:
        st.caption("No additional source metadata is available.")

st.markdown("### Indexed chunks")
page_size = 10
try:
    first_page = client.get_chunks(source_id, limit=page_size, offset=0)
except SourceServiceError as exc:
    st.error(exc.user_message)
    st.stop()

page_total = chunk_page_count(first_page.total, page_size)
selected_page = st.number_input(
    "Chunk page",
    min_value=1,
    max_value=page_total,
    value=1,
    step=1,
)

if selected_page == 1:
    chunk_page = first_page
else:
    try:
        chunk_page = client.get_chunks(
            source_id,
            limit=page_size,
            offset=(selected_page - 1) * page_size,
        )
    except SourceServiceError as exc:
        st.error(exc.user_message)
        st.stop()

st.caption(
    f"Showing {format_count(len(chunk_page.items))} of {format_count(chunk_page.total)} chunks."
)

for chunk in chunk_page.items:
    index = chunk.get("chunk_index")
    title = f"Chunk {index}" if isinstance(index, int) else "Chunk"
    section = chunk.get("section") or chunk.get("chapter")
    if isinstance(section, str) and section.strip():
        title += f" · {section.strip()}"

    with st.expander(title):
        st.caption(
            f"{page_range_label(chunk)} · "
            f"{format_count(chunk.get('token_count'))} tokens · "
            f"{chunk.get('embedding_model', 'model not recorded')}"
        )
        headings = chunk.get("heading_path")
        if isinstance(headings, list) and headings:
            values = [str(item).strip() for item in headings if str(item).strip()]
            if values:
                st.markdown("**Heading path:** " + " → ".join(values))
        content = chunk.get("content")
        if isinstance(content, str) and content.strip():
            st.text_area(
                "Chunk content",
                value=content,
                height=220,
                disabled=True,
                key=f"chunk-content-{chunk.get('id')}",
            )
        else:
            st.caption("This chunk contains no displayable text.")

st.info(
    "This workspace is read-only. Upload, re-ingestion, archive, restore "
    "and deletion controls require later validation and audit safeguards."
)
