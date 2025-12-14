"""Ingestion pipeline for PDF documents."""

from splunkbot.ingestion.chunker import Chunk, chunk_pages
from splunkbot.ingestion.embeddings import embed_texts
from splunkbot.ingestion.pdf import extract_pdf

__all__ = ["extract_pdf", "chunk_pages", "Chunk", "embed_texts"]
