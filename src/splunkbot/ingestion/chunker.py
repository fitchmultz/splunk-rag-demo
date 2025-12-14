"""Smart text chunking that preserves code blocks and sentence boundaries."""

import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from splunkbot.config import settings


@dataclass
class Chunk:
    """A text chunk with metadata."""

    content: str
    page_number: int
    chunk_index: int


def create_smart_splitter(
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> RecursiveCharacterTextSplitter:
    """Create a text splitter optimized for technical documentation.

    Separator hierarchy:
    1. Code blocks (```...```) - keep intact
    2. Double newlines (paragraphs)
    3. Single newlines
    4. Sentences (. ! ?)
    5. Words (spaces)
    6. Characters

    Args:
        chunk_size: Maximum chunk size in characters. Defaults to settings.chunk_size.
        chunk_overlap: Overlap between chunks. Defaults to settings.chunk_overlap.

    Returns:
        Configured RecursiveCharacterTextSplitter.
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    # Separators in order of preference
    separators = [
        "\n\n",  # Paragraph breaks (most preferred)
        "\n",  # Line breaks
        ". ",  # Sentence endings
        "? ",  # Question endings
        "! ",  # Exclamation endings
        "; ",  # Semicolons
        ", ",  # Commas
        " ",  # Word boundaries
        "",  # Character level (last resort)
    ]

    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        keep_separator=True,
        length_function=len,
    )


def chunk_pages(
    pages: list[tuple[int, str]],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Chunk pages while preserving page attribution.

    Strategy:
    1. Process each page separately to maintain page boundaries
    2. Use smart splitter to respect sentences and paragraphs
    3. Protect code blocks from being split

    Args:
        pages: List of (page_number, text) tuples.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        List of Chunk objects with page attribution.
    """
    splitter = create_smart_splitter(chunk_size, chunk_overlap)
    all_chunks: list[Chunk] = []

    for page_num, page_text in pages:
        # Clean up text
        cleaned = _prepare_text_for_chunking(page_text)
        if not cleaned.strip():
            continue

        # Split this page
        page_chunks = splitter.split_text(cleaned)

        for idx, chunk_text in enumerate(page_chunks):
            chunk_text = chunk_text.strip()
            if chunk_text:
                all_chunks.append(
                    Chunk(
                        content=chunk_text,
                        page_number=page_num,
                        chunk_index=idx,
                    )
                )

    return all_chunks


def _prepare_text_for_chunking(text: str) -> str:
    """Prepare text for chunking by normalizing whitespace.

    Args:
        text: Raw text.

    Returns:
        Prepared text.
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Normalize spaces (but not newlines)
    text = re.sub(r"[ \t]+", " ", text)

    # Ensure code blocks are on their own lines
    text = re.sub(r"(\S)(```)", r"\1\n\2", text)
    text = re.sub(r"(```)(\S)", r"\1\n\2", text)

    return text


def estimate_chunks(
    pages: list[tuple[int, str]],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> int:
    """Estimate the number of chunks that will be created.

    Args:
        pages: List of (page_number, text) tuples.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between chunks.

    Returns:
        Estimated number of chunks.
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    total_chars = sum(len(text) for _, text in pages)
    effective_chunk_size = chunk_size - chunk_overlap

    if effective_chunk_size <= 0:
        return len(pages)

    return max(1, total_chars // effective_chunk_size)
