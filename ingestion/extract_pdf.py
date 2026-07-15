"""Extract text from PDF documents."""

import logging
from pathlib import Path

import pypdf

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text
    """
    try:
        pdf_path = Path(file_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        text_parts = []

        with open(pdf_path, "rb") as file:
            pdf_reader = pypdf.PdfReader(file)

            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")

        full_text = "\n\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters from {file_path}")

        return full_text

    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
        raise


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from a DOCX file.

    Args:
        file_path: Path to the DOCX file

    Returns:
        Extracted text
    """
    try:
        from docx import Document

        doc = Document(file_path)
        text_parts = [paragraph.text for paragraph in doc.paragraphs]

        full_text = "\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters from {file_path}")

        return full_text

    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}", exc_info=True)
        raise


def extract_text(file_path: str) -> str:
    """
    Extract text from a file based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        Extracted text
    """
    file_path = Path(file_path)

    if file_path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(str(file_path))
    elif file_path.suffix.lower() == ".docx":
        return extract_text_from_docx(str(file_path))
    elif file_path.suffix.lower() == ".txt":
        return file_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")
