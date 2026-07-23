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
