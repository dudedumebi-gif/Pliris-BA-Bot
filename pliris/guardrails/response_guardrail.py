import logging
import re

logger = logging.getLogger(__name__)


class ResponseGuardrail:
    """Apply guardrails to generated responses."""

    def __init__(self):
        # Patterns to filter from responses
        self.forbidden_patterns = [
            r"i (don\'t|do not) (have|know) (access|information)",
            r"i cannot (answer|help|provide)",
            r"i\'m (not able|unable) to",
            r"as an (ai|language model)",
            r"i (don\'t|do not) have personal opinions",
        ]

    async def guard(self, response: str) -> str:
        """
        Apply guardrails to a response.

        Args:
            response: Generated response

        Returns:
            Guarded response
        """
        # Check for refusal patterns
        if self._contains_refusal(response):
            logger.warning("Refusal pattern detected in response")
            response = self._rewrite_refusal(response)

        # Check for harmful content
        if self._contains_harmful_content(response):
            logger.warning("Potentially harmful content detected")
            response = self._sanitize_response(response)

        # Check for PII
        if self._contains_pii(response):
            logger.warning("Potential PII detected")
            response = self._redact_pii(response)

        return response

    def _contains_refusal(self, response: str) -> bool:
        """Check if response contains refusal patterns."""
        response_lower = response.lower()
        return any(re.search(pattern, response_lower) for pattern in self.forbidden_patterns)

    def _rewrite_refusal(self, response: str) -> str:
        """Rewrite refusal to be more helpful."""
        return (
            "Based on the available documents, I don't have sufficient information "
            "to provide a complete answer to this question. You may want to "
            "rephrase your question or provide additional context."
        )

    def _contains_harmful_content(self, response: str) -> bool:
        """Check for harmful content (placeholder)."""
        # In production, implement actual harmful content detection
        return False

    def _sanitize_response(self, response: str) -> str:
        """Sanitize harmful content."""
        return response

    def _contains_pii(self, response: str) -> bool:
        """Check for personally identifiable information."""
        # Simple email pattern
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        if re.search(email_pattern, response):
            return True

        # Simple phone pattern
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        return bool(re.search(phone_pattern, response))

    def _redact_pii(self, response: str) -> str:
        """Redact PII from response."""
        # Redact emails
        response = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED EMAIL]", response
        )

        # Redact phone numbers
        response = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[REDACTED PHONE]", response)

        return response
