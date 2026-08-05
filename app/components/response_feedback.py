from __future__ import annotations

from typing import Any

import streamlit as st

from app.components.chat_message import render_copy_action
from app.response_feedback import feedback_state_key, response_feedback_target
from app.services.feedback_client import FeedbackClient, FeedbackServiceError


def render_response_feedback(
    message: dict[str, Any],
    *,
    client: FeedbackClient,
    session_id: str,
) -> None:
    """Render response-bound thumbs and optional structured feedback."""

    target = response_feedback_target(message)
    message_content = message.get("content")
    if target is None:
        if isinstance(message_content, str):
            fallback_key = (
                f"assistant-unrated:{message.get('conversation_id')}:{message_content}"
            )
            render_copy_action(
                message_content,
                key=fallback_key,
                label="Copy response",
            )
        return

    state_key = feedback_state_key(target.assistant_message_id)
    state = st.session_state.get(state_key)
    if not isinstance(state, dict):
        state = {}
        st.session_state[state_key] = state

    st.caption("Was this response helpful?")
    copy, positive, negative, _ = st.columns([0.6, 1, 1, 4])
    with copy:
        if isinstance(message_content, str):
            render_copy_action(
                message_content,
                key=f"assistant-{target.assistant_message_id}",
                label="Copy response",
            )
    with positive:
        helpful = st.button(
            "👍 Helpful",
            key=f"{state_key}_positive",
            use_container_width=True,
            type="primary" if state.get("rating") == 1 else "secondary",
        )
    with negative:
        not_helpful = st.button(
            "👎 Not helpful",
            key=f"{state_key}_negative",
            use_container_width=True,
            type="primary" if state.get("rating") == -1 else "secondary",
        )

    selected_rating = 1 if helpful else -1 if not_helpful else None
    if selected_rating is not None:
        _submit_feedback(
            client=client,
            target=target,
            session_id=session_id,
            state=state,
            state_key=state_key,
            rating=selected_rating,
            citation_helpful=state.get("citation_helpful"),
            scope_decision_correct=state.get("scope_decision_correct"),
            comment=state.get("comment"),
        )

    if state.get("rating") in {-1, 1}:
        st.caption("Feedback saved. You can add details or change your rating.")

        with st.expander("Add or update feedback details"):
            with st.form(f"{state_key}_details"):
                citation_label = "Not answered"
                if state.get("citation_helpful") is True:
                    citation_label = "Yes"
                elif state.get("citation_helpful") is False:
                    citation_label = "No"

                citation_choice = None
                if target.has_citations:
                    citation_choice = st.selectbox(
                        "Were the citations helpful?",
                        ["Not answered", "Yes", "No"],
                        index=["Not answered", "Yes", "No"].index(citation_label),
                    )

                scope_label = "Not answered"
                if state.get("scope_decision_correct") is True:
                    scope_label = "Yes"
                elif state.get("scope_decision_correct") is False:
                    scope_label = "No"

                scope_choice = st.selectbox(
                    "Did Pliris understand the question's scope correctly?",
                    ["Not answered", "Yes", "No"],
                    index=["Not answered", "Yes", "No"].index(scope_label),
                )
                comment = st.text_area(
                    "Comment (optional)",
                    value=str(state.get("comment") or ""),
                    max_chars=1000,
                    placeholder="What worked well, or what should Pliris improve?",
                )
                submitted = st.form_submit_button("Save feedback details")

            if submitted:
                _submit_feedback(
                    client=client,
                    target=target,
                    session_id=session_id,
                    state=state,
                    state_key=state_key,
                    rating=int(state["rating"]),
                    citation_helpful=_optional_boolean(citation_choice),
                    scope_decision_correct=_optional_boolean(scope_choice),
                    comment=comment,
                )


def _submit_feedback(
    *,
    client: FeedbackClient,
    target: Any,
    session_id: str,
    state: dict[str, Any],
    state_key: str,
    rating: int,
    citation_helpful: bool | None,
    scope_decision_correct: bool | None,
    comment: str | None,
) -> None:
    try:
        receipt = client.submit(
            conversation_id=target.conversation_id,
            assistant_message_id=target.assistant_message_id,
            rating=rating,
            session_id=session_id,
            citation_helpful=citation_helpful,
            scope_decision_correct=scope_decision_correct,
            comment=comment,
        )
    except FeedbackServiceError as exc:
        st.error(exc.user_message)
        if exc.retry_after_seconds is not None:
            st.caption(f"Try again in approximately {exc.retry_after_seconds} seconds.")
        return

    state.update(
        {
            "feedback_id": receipt.id,
            "rating": receipt.rating,
            "citation_helpful": receipt.citation_helpful,
            "scope_decision_correct": receipt.scope_decision_correct,
            "comment": receipt.comment,
            "status": receipt.status,
        }
    )
    st.session_state[state_key] = state
    st.success("Thank you—your feedback was saved.")


def _optional_boolean(value: str | None) -> bool | None:
    if value == "Yes":
        return True
    if value == "No":
        return False
    return None
