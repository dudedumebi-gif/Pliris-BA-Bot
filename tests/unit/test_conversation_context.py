from pliris.agents.conversation_context import (
    ConversationContextResolver,
)


def test_follow_up_is_resolved_against_previous_user_question() -> None:
    resolver = ConversationContextResolver()
    history = [
        {
            "role": "user",
            "content": ("What is requirements traceability, and why is it important?"),
        },
        {
            "role": "assistant",
            "content": "Traceability links requirements to delivery [S1].",
        },
    ]

    result = resolver.resolve(
        "Give me a practical example based on the explanation you just provided.",
        history,
    )

    assert result.context_used is True
    assert "requirements traceability" in result.scope_query
    assert "Current follow-up request" in result.retrieval_query
    assert "Previous question" in result.generation_question
    assert result.history_message_count == 2


def test_standalone_message_is_not_forced_into_previous_context() -> None:
    resolver = ConversationContextResolver()
    message = "What ingredients should I use to bake a cake?"

    result = resolver.resolve(
        message,
        [
            {
                "role": "user",
                "content": "What is requirements traceability?",
            }
        ],
    )

    assert result.context_used is False
    assert result.scope_query == message
    assert result.retrieval_query == message
    assert result.generation_question == message


def test_follow_up_without_prior_user_message_remains_standalone() -> None:
    resolver = ConversationContextResolver()
    message = "Explain that in more detail."

    result = resolver.resolve(
        message,
        [{"role": "assistant", "content": "An answer."}],
    )

    assert result.context_used is False


def test_scope_clarification_reply_is_state_resolved_deterministically() -> None:
    resolver = ConversationContextResolver()
    history = [
        {"role": "user", "content": "What does an analyst do?"},
        {
            "role": "assistant",
            "content": "Please clarify the practice.",
            "scope_status": "borderline",
        },
    ]

    first = resolver.resolve(
        "I'm talking about a financial business analyst.",
        history,
    )
    second = resolver.resolve(
        "I'm talking about a financial business analyst.",
        history,
    )

    assert first == second
    assert first.context_used is True
    assert "What does an analyst do?" in first.scope_query
    assert "financial business analyst" in first.scope_query
    assert "What does an analyst do?" in first.retrieval_query
    assert "financial business analyst" in first.retrieval_query


def test_unmarked_assistant_does_not_force_clarification_context() -> None:
    resolver = ConversationContextResolver()
    message = "I'm talking about a financial business analyst."

    result = resolver.resolve(
        message,
        [
            {"role": "user", "content": "What does an analyst do?"},
            {"role": "assistant", "content": "An ordinary answer."},
        ],
    )

    assert result.context_used is False
    assert result.scope_query == message
