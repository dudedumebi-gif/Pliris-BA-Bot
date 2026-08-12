from uuid import uuid4

import pytest

from api.conversation_tokens import (
    ConversationAccessDenied,
    ConversationTokenManager,
    MalformedConversationToken,
)


def test_conversation_token_round_trip_for_same_session() -> None:
    manager = ConversationTokenManager("test-secret")
    session_id = str(uuid4())

    token = manager.issue(session_id)

    assert manager.validate(token, session_id) == token


def test_conversation_token_rejects_another_guest_session() -> None:
    manager = ConversationTokenManager("test-secret")
    token = manager.issue(str(uuid4()))

    with pytest.raises(ConversationAccessDenied):
        manager.validate(token, str(uuid4()))


@pytest.mark.parametrize(
    "token",
    [
        "",
        "conv-1",
        "v2.invalid.signature",
        "v1.not-a-uuid.signature",
        "v1.too.many.parts",
    ],
)
def test_conversation_token_rejects_malformed_values(token: str) -> None:
    manager = ConversationTokenManager("test-secret")

    with pytest.raises(MalformedConversationToken):
        manager.validate(token, str(uuid4()))
