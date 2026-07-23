from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_CITATION_MARKER = re.compile(r"\[S\d+\]")
_FOLLOW_UP_PATTERNS = (
    re.compile(r"\b(previous|above|earlier)\s+(answer|response|explanation)\b", re.I),
    re.compile(r"\b(you|we)\s+just\s+(provided|discussed|explained|covered)\b", re.I),
    re.compile(r"\bbased\s+on\s+(that|this|the\s+explanation)\b", re.I),
    re.compile(r"\b(that|this)\s+(answer|response|explanation|example)\b", re.I),
    re.compile(r"\b(give|show|provide)\s+me\s+(another|a|an)\s+.*example\b", re.I),
    re.compile(r"\b(expand|elaborate)\s+on\s+(that|this|it)\b", re.I),
    re.compile(r"\b(summarize|explain|clarify)\s+(that|this|it)\b", re.I),
    re.compile(r"\bwhat\s+about\s+(that|this|the\s+second|the\s+first)\b", re.I),
    re.compile(r"\bhow\s+does\s+(that|this|it)\b", re.I),
)


@dataclass(frozen=True, slots=True)
class ConversationResolution:
    """A current message resolved against a bounded recent conversation."""

    original_message: str
    scope_query: str
    retrieval_query: str
    generation_question: str
    context_used: bool
    history_message_count: int

    def metadata(self) -> dict[str, Any]:
        return {
            "context_used": self.context_used,
            "history_message_count": self.history_message_count,
        }


class ConversationContextResolver:
    """Resolve explicit follow-ups without an additional model call."""

    def __init__(
        self,
        *,
        max_history_messages: int = 6,
        max_message_characters: int = 1_200,
    ) -> None:
        if not 2 <= max_history_messages <= 12:
            raise ValueError("max_history_messages must be between 2 and 12")
        if not 200 <= max_message_characters <= 4_000:
            raise ValueError("max_message_characters must be between 200 and 4000")
        self.max_history_messages = max_history_messages
        self.max_message_characters = max_message_characters

    def resolve(
        self,
        message: str,
        history: list[dict[str, Any]] | None,
    ) -> ConversationResolution:
        """Return the original or a context-resolved standalone question."""

        normalized_message = " ".join(message.split())
        bounded_history = self._bounded_history(history or [])

        if not bounded_history or not self._is_follow_up(normalized_message):
            return ConversationResolution(
                original_message=normalized_message,
                scope_query=normalized_message,
                retrieval_query=normalized_message,
                generation_question=normalized_message,
                context_used=False,
                history_message_count=len(bounded_history),
            )

        previous_user = self._latest_content(
            bounded_history,
            role="user",
        )
        if previous_user is None:
            return ConversationResolution(
                original_message=normalized_message,
                scope_query=normalized_message,
                retrieval_query=normalized_message,
                generation_question=normalized_message,
                context_used=False,
                history_message_count=len(bounded_history),
            )

        previous_user = _CITATION_MARKER.sub("", previous_user)
        resolved = (
            f"Previous Business Analysis conversation question: "
            f"{previous_user}\n"
            f"Current follow-up request: {normalized_message}"
        )

        return ConversationResolution(
            original_message=normalized_message,
            scope_query=resolved,
            retrieval_query=resolved,
            generation_question=(
                "Answer the current follow-up as a continuation of the "
                "previous question. Use only the supplied knowledge-base "
                "context.\n\n"
                f"Previous question: {previous_user}\n"
                f"Current follow-up: {normalized_message}"
            ),
            context_used=True,
            history_message_count=len(bounded_history),
        )

    def _bounded_history(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for message in history[-self.max_history_messages :]:
            role = message.get("role")
            content = message.get("content")
            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str):
                continue

            cleaned = " ".join(content.split())
            if not cleaned:
                continue
            normalized.append(
                {
                    "role": role,
                    "content": cleaned[: self.max_message_characters],
                }
            )
        return normalized

    @staticmethod
    def _is_follow_up(message: str) -> bool:
        return any(pattern.search(message) for pattern in _FOLLOW_UP_PATTERNS)

    @staticmethod
    def _latest_content(
        history: list[dict[str, str]],
        *,
        role: str,
    ) -> str | None:
        for message in reversed(history):
            if message["role"] == role:
                return message["content"]
        return None
