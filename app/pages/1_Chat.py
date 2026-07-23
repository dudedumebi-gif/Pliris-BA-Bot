from __future__ import annotations

from uuid import uuid4

import streamlit as st

from app.chat_state import discard_failed_user_turn
from app.components.chat_message import (
    render_assistant_message,
    render_user_message,
)
from app.services.chat_client import ChatClient, ChatServiceError
from app.ui_config import UIMode, load_ui_settings

settings = load_ui_settings()

if "pliris_messages" not in st.session_state:
    st.session_state.pliris_messages = []

if "pliris_conversation_id" not in st.session_state:
    st.session_state.pliris_conversation_id = None

if "pliris_guest_session_id" not in st.session_state:
    st.session_state.pliris_guest_session_id = str(uuid4())

st.title("💬 Pliris BA Bot")
st.write(
    "Ask a question about Business Analysis, Business Systems Analysis, or Project Management."
)

with st.sidebar:
    st.markdown("### Pliris")
    if settings.ui_mode is UIMode.PUBLIC:
        st.caption("Public review session")
    else:
        st.caption("Developer chat workspace")

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.pliris_messages = []
        st.session_state.pliris_conversation_id = None
        st.rerun()

    st.caption(
        "Clearing the conversation does not reset public usage limits for this browser session."
    )

if not st.session_state.pliris_messages:
    st.info(
        "Try asking about requirements elicitation, stakeholder analysis, "
        "traceability, process modelling, acceptance criteria, delivery "
        "planning, or project risks."
    )

for message in st.session_state.pliris_messages:
    if message["role"] == "user":
        render_user_message(message["content"])
        continue

    render_assistant_message(
        message["content"],
        citations=message.get("citations"),
        confidence=message.get("confidence"),
    )

    if message.get("insufficient_evidence"):
        st.info(
            "Pliris did not find enough grounded evidence in the available "
            "knowledge base for that answer."
        )

    if settings.ui_mode is UIMode.DEVELOPER:
        with st.expander("Developer response details"):
            st.json(
                {
                    "scope": message.get("scope"),
                    "conversation_id": message.get("conversation_id"),
                    "metadata": message.get("metadata", {}),
                }
            )

prompt = st.chat_input(
    "Ask Pliris a BA, BSA, or PM question",
    max_chars=2000,
)

if prompt:
    st.session_state.pliris_messages.append({"role": "user", "content": prompt})
    render_user_message(prompt)

    client = ChatClient(settings)

    with st.spinner("Reviewing the knowledge base and preparing a grounded response..."):
        try:
            reply = client.send_message(
                message=prompt,
                conversation_id=st.session_state.pliris_conversation_id,
                session_id=st.session_state.pliris_guest_session_id,
            )
        except ChatServiceError as exc:
            discard_failed_user_turn(
                st.session_state.pliris_messages,
                prompt,
            )
            st.error(exc.user_message)
            if exc.retry_after_seconds is not None:
                st.caption(f"Try again in approximately {exc.retry_after_seconds} seconds.")
        else:
            st.session_state.pliris_conversation_id = reply.conversation_id
            assistant_message = {
                "role": "assistant",
                "content": reply.response,
                "citations": reply.citations,
                "confidence": reply.confidence,
                "scope": reply.scope,
                "conversation_id": reply.conversation_id,
                "metadata": reply.metadata,
                "insufficient_evidence": bool(reply.metadata.get("insufficient_evidence", False)),
            }
            st.session_state.pliris_messages.append(assistant_message)

            render_assistant_message(
                assistant_message["content"],
                citations=assistant_message["citations"],
                confidence=assistant_message["confidence"],
            )

            if assistant_message["insufficient_evidence"]:
                st.info(
                    "Pliris did not find enough grounded evidence in the "
                    "available knowledge base for that answer."
                )

            if settings.ui_mode is UIMode.DEVELOPER:
                with st.expander("Developer response details"):
                    st.json(
                        {
                            "scope": reply.scope,
                            "conversation_id": reply.conversation_id,
                            "metadata": reply.metadata,
                        }
                    )
