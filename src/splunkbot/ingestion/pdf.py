"""PDF text extraction using PyMuPDF."""

from pathlib import Path

import fitz  # PyMuPDF


def extract_pdf(pdf_path: Path | str) -> list[tuple[int, str]]:
    """Extract text from a PDF file, preserving page boundaries.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of (page_number, text) tuples. Page numbers are 1-indexed.
    """
    pdf_path = Path(pdf_path)
    pages: list[tuple[int, str]] = []

    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            # Extract text with layout preservation
            text = page.get_text("text")

            # Clean up the text
            text = _clean_page_text(text)

            if text.strip():
                pages.append((page_num, text))

    return pages


def _clean_page_text(text: str) -> str:
    """Clean extracted page text.

    Args:
        text: Raw extracted text.

    Returns:
        Cleaned text.
    """
    import re

    # Normalize whitespace but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove common page header/footer patterns
    text = re.sub(r"^Page \d+ of \d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)  # Standalone page numbers

    return text.strip()


def get_pdf_metadata(pdf_path: Path | str) -> dict:
    """Get metadata from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary with PDF metadata.
    """
    pdf_path = Path(pdf_path)

    with fitz.open(pdf_path) as doc:
        return {
            "page_count": len(doc),
            "title": doc.metadata.get("title", ""),
            "author": doc.metadata.get("author", ""),
            "subject": doc.metadata.get("subject", ""),
            "creator": doc.metadata.get("creator", ""),
        }
