from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache
from uuid import UUID, uuid4

from api.guest_access import get_guest_access_policy

TOKEN_VERSION = "v1"


class ConversationTokenError(ValueError):
    """Base error for invalid public conversation tokens."""


class MalformedConversationToken(ConversationTokenError):
    """Raised when a token does not match the supported structure."""


class ConversationAccessDenied(ConversationTokenError):
    """Raised when a token is valid but belongs to another guest session."""


class ConversationTokenManager:
    """Issue and validate opaque conversation tokens bound to one guest session."""

    def __init__(self, secret: str | bytes) -> None:
        raw_secret = secret.encode("utf-8") if isinstance(secret, str) else secret
        if not raw_secret:
            raise ValueError("conversation token secret must not be empty")
        self._secret = raw_secret

    def issue(self, session_id: str) -> str:
        """Create a new signed conversation token for one anonymous session."""

        normalized_session = str(UUID(session_id))
        conversation_id = uuid4().hex
        signature = self._signature(
            session_id=normalized_session,
            conversation_id=conversation_id,
        )
        return f"{TOKEN_VERSION}.{conversation_id}.{signature}"

    def validate(self, token: str, session_id: str) -> str:
        """Validate structure and ownership, returning the canonical token."""

        normalized_session = str(UUID(session_id))
        parts = token.strip().split(".")
        if len(parts) != 3 or parts[0] != TOKEN_VERSION:
            raise MalformedConversationToken("Conversation identifier is not valid.")

        conversation_id = parts[1]
        signature = parts[2]
        try:
            parsed = UUID(hex=conversation_id)
        except ValueError as exc:
            raise MalformedConversationToken("Conversation identifier is not valid.") from exc

        canonical_id = parsed.hex
        expected = self._signature(
            session_id=normalized_session,
            conversation_id=canonical_id,
        )
        if not hmac.compare_digest(signature, expected):
            raise ConversationAccessDenied("Conversation access is not authorized.")

        return f"{TOKEN_VERSION}.{canonical_id}.{expected}"

    def _signature(
        self,
        *,
        session_id: str,
        conversation_id: str,
    ) -> str:
        payload = f"{TOKEN_VERSION}:{session_id}:{conversation_id}".encode()
        digest = hmac.new(
            self._secret,
            payload,
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")


@lru_cache(maxsize=1)
def get_conversation_token_manager() -> ConversationTokenManager:
    """Return the process-level conversation-token signer."""

    policy = get_guest_access_policy()
    secret = policy.shared_secret or secrets.token_urlsafe(32)
    return ConversationTokenManager(secret)
