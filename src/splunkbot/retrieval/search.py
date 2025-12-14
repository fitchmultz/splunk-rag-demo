"""Hybrid search combining vector similarity and keyword search with RRF fusion."""

from dataclasses import dataclass

import asyncpg
import numpy as np

from splunkbot.config import settings


@dataclass
class SearchResult:
    """A search result with metadata."""

    chunk_id: int
    document_id: int
    filename: str
    page_number: int
    content: str
    rrf_score: float


# SQL query for hybrid search with Reciprocal Rank Fusion (RRF)
# This combines semantic (vector) search with keyword (full-text) search
HYBRID_SEARCH_QUERY = """
WITH semantic_search AS (
    SELECT
        c.id,
        c.document_id,
        d.filename,
        c.page_number,
        c.content,
        ROW_NUMBER() OVER (ORDER BY c.embedding <=> $1::vector) AS rank
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    ORDER BY c.embedding <=> $1::vector
    LIMIT 20
),
keyword_search AS (
    SELECT
        c.id,
        c.document_id,
        d.filename,
        c.page_number,
        c.content,
        ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.search_vector, query) DESC) AS rank
    FROM chunks c
    JOIN documents d ON c.document_id = d.id,
         plainto_tsquery('english', $2) query
    WHERE c.search_vector @@ query
    ORDER BY ts_rank_cd(c.search_vector, query) DESC
    LIMIT 20
)
SELECT
    COALESCE(s.id, k.id) AS chunk_id,
    COALESCE(s.document_id, k.document_id) AS document_id,
    COALESCE(s.filename, k.filename) AS filename,
    COALESCE(s.page_number, k.page_number) AS page_number,
    COALESCE(s.content, k.content) AS content,
    COALESCE(1.0 / ($3::float + s.rank), 0.0) +
    COALESCE(1.0 / ($3::float + k.rank), 0.0) AS rrf_score
FROM semantic_search s
FULL OUTER JOIN keyword_search k ON s.id = k.id
ORDER BY rrf_score DESC
LIMIT $4;
"""

# Fallback to semantic-only search when no keyword matches
SEMANTIC_ONLY_QUERY = """
SELECT
    c.id AS chunk_id,
    c.document_id,
    d.filename,
    c.page_number,
    c.content,
    1.0 / ($2::float + ROW_NUMBER() OVER (ORDER BY c.embedding <=> $1::vector)) AS rrf_score
FROM chunks c
JOIN documents d ON c.document_id = d.id
ORDER BY c.embedding <=> $1::vector
LIMIT $3;
"""


async def hybrid_search(
    pool: asyncpg.Pool,
    query_embedding: np.ndarray,
    query_text: str,
    top_k: int | None = None,
    rrf_k: int | None = None,
) -> list[SearchResult]:
    """Perform hybrid search combining vector and keyword search.

    Uses Reciprocal Rank Fusion (RRF) to combine results from both
    semantic (vector) and keyword (full-text) search. RRF is robust
    and doesn't require score normalization.

    Args:
        pool: Asyncpg connection pool.
        query_embedding: Query embedding vector (1024 dims for bge-m3).
        query_text: Original query text for keyword search.
        top_k: Number of results to return. Defaults to settings.top_k_results.
        rrf_k: RRF constant (typically 60). Defaults to settings.rrf_k.

    Returns:
        List of SearchResult objects sorted by RRF score.
    """
    top_k = top_k or settings.top_k_results
    rrf_k = rrf_k or settings.rrf_k

    async with pool.acquire() as conn:
        # Try hybrid search first
        rows = await conn.fetch(
            HYBRID_SEARCH_QUERY,
            query_embedding.tolist(),  # $1: embedding
            query_text,  # $2: query text
            float(rrf_k),  # $3: RRF k constant
            top_k,  # $4: limit
        )

        # If no results (e.g., no keyword matches), fall back to semantic only
        if not rows:
            rows = await conn.fetch(
                SEMANTIC_ONLY_QUERY,
                query_embedding.tolist(),  # $1: embedding
                float(rrf_k),  # $2: RRF k constant
                top_k,  # $3: limit
            )

        return [
            SearchResult(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                filename=row["filename"],
                page_number=row["page_number"],
                content=row["content"],
                rrf_score=float(row["rrf_score"]),
            )
            for row in rows
        ]


def format_results_for_context(results: list[SearchResult]) -> str:
    """Format search results as numbered context blocks for the LLM.

    Args:
        results: List of search results.

    Returns:
        Formatted context string with source citations.
    """
    blocks = []
    for i, r in enumerate(results, 1):
        # Format manual name: "Splunk-9.4.2-Admin.pdf" -> "Splunk 9.4.2 Admin"
        manual_name = r.filename.replace(".pdf", "").replace("-", " ").replace("_", " ")
        blocks.append(f"[{i}] Source: {manual_name} p.{r.page_number}\n{r.content}")

    return "\n\n---\n\n".join(blocks)


def format_source_citation(result: SearchResult) -> str:
    """Format a single result as a source citation.

    Args:
        result: A search result.

    Returns:
        Citation string like "[Splunk 9.4.2 Admin p.42]"
    """
    manual_name = result.filename.replace(".pdf", "").replace("-", " ").replace("_", " ")
    return f"[{manual_name} p.{result.page_number}]"
