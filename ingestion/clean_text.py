"""Clean and normalize extracted text."""

import logging
import re

logger = logging.getLogger(__name__)


def clean_document_text(text: str) -> str:
    """
    Clean and normalize document text.

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove page numbers and headers/footers (simple patterns)
    text = re.sub(r"\n\s*\d+\s*\n", "\n", text)

    # Remove special characters that might cause issues
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(""", "'").replace(""", "'")

    # Normalize dashes
    text = re.sub(r"\u2013", "-", text)
    text = re.sub(r"\u2014", "--", text)

    # Remove empty lines
    text = re.sub(r"\n\s*\n", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    logger.info(f"Cleaned text: {len(text)} characters")

    return text


def remove_headers_footers(text: str, patterns: list | None = None) -> str:
    """
    Remove headers and footers based on patterns.

    Args:
        text: Document text
        patterns: List of regex patterns to match headers/footers

    Returns:
        Text with headers/footers removed
    """
    if not patterns:
        # Default patterns for common headers/footers
        patterns = [
            r"^Page \d+ of \d+$",
            r"^\d+$",
            r"^Confidential",
            r"^Draft",
        ]

    lines = text.split("\n")
    filtered_lines = []

    for line in lines:
        is_header_footer = False
        for pattern in patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                is_header_footer = True
                break

        if not is_header_footer:
            filtered_lines.append(line)

    return "\n".join(filtered_lines)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Args:
        text: Input text

    Returns:
        Text with normalized whitespace
    """
    # Replace tabs with spaces
    text = text.replace("\t", " ")

    # Remove multiple spaces
    text = re.sub(r" +", " ", text)

    # Normalize line endings
    text = re.sub(r"\r\n", "\n", text)

    return text
