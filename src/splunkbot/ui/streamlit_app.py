"""Streamlit chat interface for splunkbot."""

import asyncio

import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="Splunk Documentation Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_stats():
    """Get database statistics."""
    from splunkbot.db.connection import close_pool, get_pool

    async def fetch():
        try:
            pool = await get_pool()
            docs = await pool.fetchval("SELECT COUNT(*) FROM documents")
            chunks = await pool.fetchval("SELECT COUNT(*) FROM chunks")
            convs = await pool.fetchval("SELECT COUNT(*) FROM conversations")
            return {"documents": docs, "chunks": chunks, "conversations": convs}
        finally:
            await close_pool()

    return asyncio.run(fetch())


def get_conversations():
    """Get recent conversations."""
    from splunkbot.chat.rag import get_conversations as fetch_convs
    from splunkbot.db.connection import close_pool

    async def fetch():
        try:
            return await fetch_convs(limit=10)
        finally:
            await close_pool()

    return asyncio.run(fetch())


def load_conversation_messages(conversation_id: int):
    """Load messages for a conversation."""
    import json

    from splunkbot.db.connection import close_pool, get_pool

    async def fetch():
        try:
            pool = await get_pool()
            rows = await pool.fetch(
                """
                SELECT role, content, sources_json
                FROM messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                """,
                conversation_id,
            )
            messages = []
            for row in rows:
                msg = {
                    "role": row["role"],
                    "content": row["content"],
                }
                if row["sources_json"]:
                    msg["sources"] = json.loads(row["sources_json"])
                messages.append(msg)
            return messages
        finally:
            await close_pool()

    return asyncio.run(fetch())


def delete_conversation(conversation_id: int):
    """Delete a conversation and its messages."""
    from splunkbot.db.connection import close_pool, get_pool

    async def delete():
        try:
            pool = await get_pool()
            # Messages are deleted via CASCADE, just delete conversation
            await pool.execute(
                "DELETE FROM conversations WHERE id = $1",
                conversation_id,
            )
        finally:
            await close_pool()

    asyncio.run(delete())


def prepare_query(query: str, conversation_id: int | None):
    """Prepare a RAG query for streaming."""
    from splunkbot.chat.rag import rag_query_prepare
    from splunkbot.db.connection import close_pool

    async def fetch():
        try:
            return await rag_query_prepare(query, conversation_id)
        finally:
            await close_pool()

    return asyncio.run(fetch())


def finalize_query(context, query: str, full_response: str, thinking: str | None = None):
    """Finalize a streaming RAG query."""
    from splunkbot.chat.rag import rag_query_finalize
    from splunkbot.db.connection import close_pool

    async def fetch():
        try:
            return await rag_query_finalize(context, query, full_response, thinking)
        finally:
            await close_pool()

    return asyncio.run(fetch())


def stream_response(context):
    """Stream the LLM response, returning stream object for thinking access."""
    from splunkbot.chat.rag import rag_query_stream

    return rag_query_stream(context)


# No custom CSS - use native Streamlit components for proper theming

# Title
st.title("📚 Splunk Documentation Assistant")

# Sidebar
with st.sidebar:
    st.header("📊 Index Status")

    try:
        stats = get_stats()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Documents", stats["documents"])
        with col2:
            st.metric("Chunks", stats["chunks"])
        st.metric("Conversations", stats["conversations"])
    except Exception as e:
        st.error(f"Database error: {e}")
        st.info("Make sure the database is running and initialized.")

    st.divider()

    st.header("💬 Conversations")

    # New conversation button
    if st.button("➕ New Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

    # Recent conversations
    try:
        conversations = get_conversations()
        if conversations:
            for conv in conversations:
                title = conv["title"][:30] + "..." if len(conv["title"]) > 33 else conv["title"]
                col1, col2 = st.columns([5, 1])
                with col1:
                    if st.button(
                        f"📝 {title}",
                        key=f"conv_{conv['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.conversation_id = conv["id"]
                        st.session_state.messages = load_conversation_messages(conv["id"])
                        st.rerun()
                with col2:
                    if st.button(
                        "🗑️",
                        key=f"del_{conv['id']}",
                        help="Delete conversation",
                    ):
                        delete_conversation(conv["id"])
                        # Clear current if we deleted the active one
                        if st.session_state.conversation_id == conv["id"]:
                            st.session_state.conversation_id = None
                            st.session_state.messages = []
                        st.rerun()
        else:
            st.caption("No conversations yet")
    except Exception as e:
        st.caption(f"Could not load conversations: {e}")

    st.divider()

    # Settings
    st.header("⚙️ Settings")
    show_thinking = st.toggle("Show model thinking", value=True, key="show_thinking")

    st.divider()

    # Clear history button
    if st.button("🗑️ Clear Chat History", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.conversation_id = None
        st.rerun()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None


def render_sources(sources: list[dict]) -> None:
    """Render sources in an expander using native Streamlit components."""
    with st.expander("📄 View Sources", expanded=False):
        for src in sources:
            manual = src["filename"].replace(".pdf", "").replace("-", " ")
            st.markdown(f"**{manual}** — Page {src['page_number']}")
            st.caption(f"Relevance: {src['score']:.3f}")
            st.divider()


def render_thinking(thinking: str) -> None:
    """Render thinking content if enabled using native Streamlit components."""
    if thinking and st.session_state.get("show_thinking", False):
        with st.expander("🧠 Model Thinking", expanded=False):
            st.caption("Internal Reasoning")
            st.markdown(thinking)


# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # Order: thinking FIRST, then content, then sources
            if message.get("thinking"):
                render_thinking(message["thinking"])
            st.markdown(message["content"])
            if message.get("sources"):
                render_sources(message["sources"])
        else:
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about Splunk..."):
    # Track if this is a new conversation (for sidebar refresh)
    is_new_conversation = st.session_state.conversation_id is None

    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response with streaming
    with st.chat_message("assistant"):
        try:
            # Prepare the query (retrieval phase)
            with st.spinner("Searching documentation..."):
                result = prepare_query(prompt, st.session_state.conversation_id)

            # Check if we got an early response (no results)
            from splunkbot.chat.rag import RAGResponse, RAGStreamContext

            if isinstance(result, RAGResponse):
                # No results found - show the response directly
                st.markdown(result.answer)
                # Update conversation_id if it was created
                if result.conversation_id:
                    st.session_state.conversation_id = result.conversation_id
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": result.answer,
                        "sources": result.sources,
                        "thinking": result.thinking,
                    }
                )
                # Refresh sidebar if this was a new conversation
                if is_new_conversation:
                    st.rerun()
            elif isinstance(result, RAGStreamContext):
                thinking_text = ""
                response_text = ""
                show_thinking = st.session_state.get("show_thinking", True)

                # Create all elements upfront in a single container
                # to prevent elements from appearing outside message bounds
                content_container = st.container()

                with content_container:
                    # Thinking expander (if enabled) - created first
                    if show_thinking:
                        thinking_expander = st.expander("🧠 Model Thinking", expanded=False)
                        thinking_placeholder = thinking_expander.empty()
                    else:
                        thinking_placeholder = None

                    # Response area
                    response_placeholder = st.empty()

                    # Sources area - use container to hold it
                    sources_area = st.container()

                # Stream content
                stream = stream_response(result)
                for chunk in stream.thinking_stream():
                    if chunk.is_thinking and chunk.thinking:
                        thinking_text += chunk.thinking
                        if thinking_placeholder:
                            thinking_placeholder.markdown(thinking_text)
                    elif chunk.content:
                        response_text += chunk.content
                        response_placeholder.markdown(response_text)

                # Finalize
                full_response = response_text
                thinking = thinking_text.strip() if thinking_text else None
                final_response = finalize_query(result, prompt, full_response, thinking)
                st.session_state.conversation_id = result.conversation_id

                # Render sources in the pre-created area
                with sources_area:
                    if final_response.sources:
                        render_sources(final_response.sources)

                # Add to history
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": full_response,
                        "sources": final_response.sources,
                        "thinking": thinking,
                    }
                )

                # Refresh sidebar if this was a new conversation
                if is_new_conversation:
                    st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
            st.info("Make sure the database is running and Ollama is available.")

# Footer
st.divider()
st.markdown(
    """
    <div style="text-align: center; opacity: 0.6; font-size: 0.8em;">
        Powered by Ollama + pgvector |
        <a href="https://www.splunk.com/en_us/resources/documentation.html"
           style="color: inherit;">Splunk Docs</a>
    </div>
    """,
    unsafe_allow_html=True,
)
