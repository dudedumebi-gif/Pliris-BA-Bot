from app.chat_state import discard_failed_user_turn


def test_discard_failed_user_turn_removes_matching_pending_message() -> None:
    messages = [
        {"role": "assistant", "content": "Earlier answer."},
        {"role": "user", "content": "Retry this question."},
    ]

    removed = discard_failed_user_turn(
        messages,
        "Retry this question.",
    )

    assert removed is True
    assert messages == [{"role": "assistant", "content": "Earlier answer."}]


def test_discard_failed_user_turn_preserves_nonmatching_history() -> None:
    messages = [{"role": "user", "content": "A different question."}]

    removed = discard_failed_user_turn(
        messages,
        "Retry this question.",
    )

    assert removed is False
    assert messages == [{"role": "user", "content": "A different question."}]
