"""Database schema definitions and initialization."""

import asyncpg

from splunkbot.config import settings

# Schema creation SQL
SCHEMA_SQL = f"""
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table: tracks ingested PDFs
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chunks table: stores text chunks with embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector({settings.embedding_dimensions}),
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, page_number, chunk_index)
);

-- Conversations table: persists chat sessions
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table: stores conversation history
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_search_vector ON chunks
    USING GIN (search_vector);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
"""

# Drop all tables SQL
DROP_SCHEMA_SQL = """
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
"""


async def init_schema(pool: asyncpg.Pool) -> None:
    """Initialize the database schema.

    Args:
        pool: The database connection pool.
    """
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def reset_schema(pool: asyncpg.Pool) -> None:
    """Drop and recreate the database schema.

    Args:
        pool: The database connection pool.
    """
    async with pool.acquire() as conn:
        await conn.execute(DROP_SCHEMA_SQL)
        await conn.execute(SCHEMA_SQL)


async def check_pgvector(pool: asyncpg.Pool) -> str | None:
    """Check if pgvector extension is available.

    Args:
        pool: The database connection pool.

    Returns:
        The installed version if available, None otherwise.
    """
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT installed_version FROM pg_available_extensions WHERE name = 'vector'"
        )
        return result
