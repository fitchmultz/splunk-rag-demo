"""RAG pipeline orchestrating retrieval and generation."""

import json
from dataclasses import dataclass

import asyncpg

from splunkbot.chat.llm import chat, chat_stream
from splunkbot.chat.prompts import NO_CONTEXT_RESPONSE, build_messages
from splunkbot.db.connection import get_pool
from splunkbot.ingestion.embeddings import embed_single
from splunkbot.retrieval.search import format_results_for_context, hybrid_search


@dataclass
class RAGResponse:
    """A RAG response with answer and sources."""

    answer: str
    sources: list[dict]  # [{filename, page_number, chunk_id, score}]
    thinking: str | None = None  # Optional thinking/reasoning content
    conversation_id: int | None = None  # Set when conversation was created/used


async def rag_query(
    query: str,
    conversation_id: int | None = None,
    pool: asyncpg.Pool | None = None,
) -> tuple[RAGResponse, int]:
    """Perform a RAG query with retrieval and generation.

    Args:
        query: The user's question.
        conversation_id: Optional conversation ID to continue.
        pool: Optional connection pool (will create one if not provided).

    Returns:
        Tuple of (RAGResponse, conversation_id).
    """
    if pool is None:
        pool = await get_pool()

    # Get or create conversation
    conversation_id = await _ensure_conversation(pool, conversation_id)

    # Get conversation history
    history = await _get_conversation_history(pool, conversation_id)

    # Generate query embedding
    query_embedding = embed_single(query)

    # Perform hybrid search
    results = await hybrid_search(pool, query_embedding, query)

    # Generate response
    if not results:
        response = RAGResponse(answer=NO_CONTEXT_RESPONSE, sources=[])
    else:
        # Format context for LLM
        context = format_results_for_context(results)

        # Build messages with history
        messages = build_messages(query, context, history)

        # Generate answer (chat now returns ChatResponse with thinking)
        chat_response = chat(messages)

        # Build sources list
        sources = [
            {
                "filename": r.filename,
                "page_number": r.page_number,
                "chunk_id": r.chunk_id,
                "score": r.rrf_score,
            }
            for r in results
        ]

        response = RAGResponse(
            answer=chat_response.content,
            sources=sources,
            thinking=chat_response.thinking,
        )

    # Save messages to database
    await _save_message(pool, conversation_id, "user", query, None)
    await _save_message(pool, conversation_id, "assistant", response.answer, response.sources)

    # Update conversation timestamp
    await _update_conversation(pool, conversation_id)

    return response, conversation_id


async def _ensure_conversation(pool: asyncpg.Pool, conversation_id: int | None) -> int:
    """Ensure a conversation exists, creating one if needed.

    Args:
        pool: Database connection pool.
        conversation_id: Optional existing conversation ID.

    Returns:
        The conversation ID.
    """
    if conversation_id is not None:
        # Verify it exists
        exists = await pool.fetchval("SELECT id FROM conversations WHERE id = $1", conversation_id)
        if exists:
            return conversation_id

    # Create new conversation
    return await pool.fetchval("INSERT INTO conversations (title) VALUES (NULL) RETURNING id")


async def _get_conversation_history(
    pool: asyncpg.Pool, conversation_id: int, limit: int = 10
) -> list[dict[str, str]]:
    """Get recent conversation history.

    Args:
        pool: Database connection pool.
        conversation_id: The conversation ID.
        limit: Maximum number of messages to retrieve.

    Returns:
        List of message dicts with 'role' and 'content'.
    """
    rows = await pool.fetch(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        conversation_id,
        limit,
    )

    # Reverse to chronological order
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


async def _save_message(
    pool: asyncpg.Pool,
    conversation_id: int,
    role: str,
    content: str,
    sources: list[dict] | None,
) -> int:
    """Save a message to the database.

    Args:
        pool: Database connection pool.
        conversation_id: The conversation ID.
        role: Message role ('user' or 'assistant').
        content: Message content.
        sources: Optional sources for assistant messages.

    Returns:
        The message ID.
    """
    sources_json = json.dumps(sources) if sources else None

    return await pool.fetchval(
        """
        INSERT INTO messages (conversation_id, role, content, sources_json)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        conversation_id,
        role,
        content,
        sources_json,
    )


async def _update_conversation(pool: asyncpg.Pool, conversation_id: int) -> None:
    """Update the conversation's updated_at timestamp.

    Args:
        pool: Database connection pool.
        conversation_id: The conversation ID.
    """
    await pool.execute(
        "UPDATE conversations SET updated_at = NOW() WHERE id = $1",
        conversation_id,
    )


async def get_conversations(pool: asyncpg.Pool | None = None, limit: int = 20) -> list[dict]:
    """Get recent conversations.

    Args:
        pool: Optional connection pool.
        limit: Maximum number of conversations.

    Returns:
        List of conversation dicts.
    """
    if pool is None:
        pool = await get_pool()

    rows = await pool.fetch(
        """
        SELECT c.id, c.title, c.created_at, c.updated_at,
               (SELECT content FROM messages m WHERE m.conversation_id = c.id
                AND m.role = 'user' ORDER BY m.created_at LIMIT 1) as first_message
        FROM conversations c
        ORDER BY c.updated_at DESC
        LIMIT $1
        """,
        limit,
    )

    results = []
    for row in rows:
        if row["title"]:
            title = row["title"]
        elif row["first_message"]:
            title = row["first_message"][:50]
        else:
            title = "New conversation"
        results.append(
            {
                "id": row["id"],
                "title": title,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return results


@dataclass
class RAGStreamContext:
    """Context for streaming RAG responses."""

    sources: list[dict]
    messages: list[dict[str, str]]
    conversation_id: int
    # Note: Don't store pool here - causes issues with multiple asyncio.run() calls


async def rag_query_prepare(
    query: str,
    conversation_id: int | None = None,
    pool: asyncpg.Pool | None = None,
) -> RAGStreamContext | RAGResponse:
    """Prepare a RAG query for streaming, returning context or early response.

    Args:
        query: The user's question.
        conversation_id: Optional conversation ID to continue.
        pool: Optional connection pool.

    Returns:
        RAGStreamContext for streaming, or RAGResponse if no results found.
    """
    if pool is None:
        pool = await get_pool()

    # Get or create conversation
    conversation_id = await _ensure_conversation(pool, conversation_id)

    # Get conversation history
    history = await _get_conversation_history(pool, conversation_id)

    # Generate query embedding
    query_embedding = embed_single(query)

    # Perform hybrid search
    results = await hybrid_search(pool, query_embedding, query)

    if not results:
        # Save messages and return early
        await _save_message(pool, conversation_id, "user", query, None)
        await _save_message(pool, conversation_id, "assistant", NO_CONTEXT_RESPONSE, None)
        await _update_conversation(pool, conversation_id)
        return RAGResponse(
            answer=NO_CONTEXT_RESPONSE, sources=[], conversation_id=conversation_id
        )

    # Format context for LLM
    context = format_results_for_context(results)
    messages = build_messages(query, context, history)

    # Build sources list
    sources = [
        {
            "filename": r.filename,
            "page_number": r.page_number,
            "chunk_id": r.chunk_id,
            "score": r.rrf_score,
        }
        for r in results
    ]

    return RAGStreamContext(
        sources=sources,
        messages=messages,
        conversation_id=conversation_id,
    )


class ThinkingAwareStream:
    """A stream wrapper that separates thinking from answer content.

    Uses Ollama's native thinking support via the think parameter.
    Thinking chunks have is_thinking=True, content chunks have is_thinking=False.
    """

    def __init__(self, messages: list[dict[str, str]]):
        self._messages = messages
        self.thinking: str = ""
        self._content_started = False

    def __iter__(self):
        """Iterate over content chunks, accumulating thinking separately."""
        for chunk in chat_stream(self._messages):
            if chunk.is_thinking and chunk.thinking:
                self.thinking += chunk.thinking
            elif chunk.content:
                self._content_started = True
                yield chunk.content

    def thinking_stream(self):
        """Iterate over all chunks, yielding both thinking and content with flags."""
        yield from chat_stream(self._messages)


def rag_query_stream(context: RAGStreamContext) -> ThinkingAwareStream:
    """Stream the LLM response for a prepared RAG query.

    Args:
        context: The prepared RAG context.

    Returns:
        A ThinkingAwareStream that yields answer chunks and captures thinking.
    """
    return ThinkingAwareStream(context.messages)


async def rag_query_finalize(
    context: RAGStreamContext,
    query: str,
    full_response: str,
    thinking: str | None = None,
) -> RAGResponse:
    """Finalize a streaming RAG query by saving to database.

    Args:
        context: The RAG context.
        query: The original query.
        full_response: The complete response text.
        thinking: Optional thinking content captured during streaming.

    Returns:
        The final RAGResponse.
    """
    # Get a fresh pool for this event loop
    pool = await get_pool()

    # Save messages to database
    await _save_message(pool, context.conversation_id, "user", query, None)
    await _save_message(pool, context.conversation_id, "assistant", full_response, context.sources)
    await _update_conversation(pool, context.conversation_id)

    return RAGResponse(answer=full_response, sources=context.sources, thinking=thinking)
