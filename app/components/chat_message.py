from base64 import b64encode
from hashlib import sha256
from html import escape

import streamlit as st

_COPY_ACTION_TEMPLATE = """
<div class="pliris-copy-action" id="__CONTAINER_ID__">
  <button type="button" aria-label="__LABEL__" title="__LABEL__">
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <rect x="8" y="8" width="11" height="11" rx="2"></rect>
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path>
    </svg>
    <span class="pliris-copy-text">Copy</span>
  </button>
  <span role="status" aria-live="polite"></span>
</div>
<style>
  .pliris-copy-action {
    align-items: center;
    display: flex;
    gap: 0.35rem;
    min-height: 2.25rem;
  }
  .pliris-copy-action button {
    align-items: center;
    background: transparent;
    background: rgba(128, 128, 128, 0.08);
    border: 1px solid rgba(128, 128, 128, 0.28);
    border-radius: 0.45rem;
    color: var(--text-color, #fafafa);
    cursor: pointer;
    display: inline-flex;
    font: inherit;
    gap: 0.35rem;
    height: 2rem;
    justify-content: center;
    min-width: 4.5rem;
    padding: 0.3rem 0.55rem;
    width: auto;
  }
  .pliris-copy-action button:hover,
  .pliris-copy-action button:focus-visible {
    background: rgba(128, 128, 128, 0.15);
    border-color: rgba(128, 128, 128, 0.25);
    outline: none;
  }
  .pliris-copy-action button.copied {
    color: #21c77a;
  }
  .pliris-copy-action svg {
    fill: none;
    height: 1.1rem;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-width: 1.8;
    width: 1.1rem;
  }
  .pliris-copy-action .pliris-copy-text {
    font-size: 0.82rem;
    font-weight: 500;
    opacity: 1;
  }
  .pliris-copy-action > span {
    font-size: 0.78rem;
    opacity: 0.8;
  }
</style>
<script>
(() => {
  const container = document.getElementById("__CONTAINER_ID__");
  const button = container?.querySelector("button");
  const status = container?.querySelector('[role="status"]');
  if (!button || !status || button.dataset.bound === "true") return;
  button.dataset.bound = "true";

  const encoded = "__ENCODED_MESSAGE__";
  const binary = atob(encoded);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const message = new TextDecoder().decode(bytes);

  const fallbackCopy = (value) => {
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error("Copy command was rejected.");
  };

  button.addEventListener("click", async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(message);
      } else {
        fallbackCopy(message);
      }
      button.classList.add("copied");
      status.textContent = "Copied";
      window.setTimeout(() => {
        button.classList.remove("copied");
        status.textContent = "";
      }, 1800);
    } catch (_error) {
      status.textContent = "Copy failed";
    }
  });
})();
</script>
"""


def copy_action_html(message: str, *, key: str, label: str) -> str:
    """Build a copy control without embedding message text as executable HTML."""

    container_id = f"pliris-copy-{sha256(key.encode('utf-8')).hexdigest()[:16]}"
    encoded_message = b64encode(message.encode("utf-8")).decode("ascii")
    return (
        _COPY_ACTION_TEMPLATE.replace("__CONTAINER_ID__", container_id)
        .replace("__ENCODED_MESSAGE__", encoded_message)
        .replace("__LABEL__", escape(label, quote=True))
    )


def render_copy_action(message: str, *, key: str, label: str) -> None:
    """Render an accessible copy-to-clipboard control for one message."""

    st.html(
        copy_action_html(message, key=key, label=label),
        width="content",
        unsafe_allow_javascript=True,
    )


def render_user_message(
    message: str,
    timestamp: str | None = None,
    *,
    copy_key: str | None = None,
) -> None:
    """Render a user chat message."""
    with st.chat_message("user"):
        st.write(message)
        if copy_key is not None:
            render_copy_action(message, key=copy_key, label="Copy request")
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
