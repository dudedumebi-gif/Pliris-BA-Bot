import logging
import re

logger = logging.getLogger(__name__)


class PromptInjectionDetector:
    """Detect potential prompt injection attempts."""

    def __init__(self):
        # Common prompt injection patterns
        self.injection_patterns = [
            r"ignore (all )?(previous|above) instructions",
            r"disregard (all )?(previous|above) instructions",
            r"forget (all )?(previous|above) instructions",
            r"override (all )?(previous|above) instructions",
            r"new instructions:",
            r"system:",
            r"admin:",
            r"developer:",
            r"print your (system )?prompt",
            r"show your (system )?prompt",
            r"reveal your (system )?prompt",
            r"output your (system )?prompt",
            r"display your (system )?prompt",
            r"what are your instructions",
            r"what are you programmed to do",
            r"what is your purpose",
            r"act as a",
            r"pretend to be",
            r"roleplay as",
            r"simulate",
            r"jailbreak",
            r"dan",
        ]

    def detect(self, query: str) -> bool:
        """
        Detect if a query contains prompt injection.

        Args:
            query: User query

        Returns:
            True if injection detected, False otherwise
        """
        query_lower = query.lower()

        for pattern in self.injection_patterns:
            if re.search(pattern, query_lower):
                logger.warning(f"Prompt injection pattern detected: {pattern}")
                return True

        # Check for excessive special characters (common in injection attempts)
        special_char_ratio = self._calculate_special_char_ratio(query)
        if special_char_ratio > 0.3:
            logger.warning(f"High special character ratio: {special_char_ratio}")
            return True

        return False

    def _calculate_special_char_ratio(self, text: str) -> float:
        """Calculate the ratio of special characters in text."""
        if not text:
            return 0.0

        special_chars = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`")
        special_count = sum(1 for char in text if char in special_chars)

        return special_count / len(text)
