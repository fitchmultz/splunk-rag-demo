"""System prompts and prompt templates for RAG."""

SYSTEM_PROMPT = """You are a helpful Splunk documentation assistant. \
Your primary role is to answer questions about Splunk using the provided \
documentation excerpts as your main source of truth.

GUIDELINES:
1. PRIORITIZE information from the provided documentation context
2. Cite sources using [Manual Name p.XX] format when referencing specific documentation
3. When the documentation provides relevant information, base your answer on it
4. If the documentation doesn't fully address the question, you may supplement \
with general Splunk knowledge, but clearly indicate when you're going beyond \
the provided sources (e.g., "Based on general Splunk knowledge..." or \
"While not in the provided documentation...")
5. For code examples from the documentation, include the source citation
6. Be concise but thorough in your explanations
7. If multiple sources discuss the same topic, synthesize them and cite all
8. If you're genuinely unsure about something, say so rather than guessing

The user's question will be followed by relevant documentation excerpts with \
citation information. Use these to provide accurate, well-sourced answers."""

USER_PROMPT_TEMPLATE = """Question: {query}

Relevant documentation:
{context}

Please answer the question, using the documentation above as your primary source. \
Cite sources using [Manual Name p.XX] format when referencing the documentation."""

NO_CONTEXT_RESPONSE = """I couldn't find relevant information about that \
in the indexed Splunk documentation.

This could mean:
- The topic isn't covered in the manuals I have access to
- Try rephrasing your question with different keywords
- The documentation might use different terminology

Would you like to try asking the question differently?"""


def build_user_message(query: str, context: str) -> str:
    """Build the user message with query and context.

    Args:
        query: The user's question.
        context: Formatted context from search results.

    Returns:
        Complete user message for the LLM.
    """
    return USER_PROMPT_TEMPLATE.format(query=query, context=context)


def build_messages(
    query: str,
    context: str,
    conversation_history: list[dict[str, str]] | None = None,
    max_history: int = 6,
) -> list[dict[str, str]]:
    """Build the complete message list for the LLM.

    Args:
        query: The user's question.
        context: Formatted context from search results.
        conversation_history: Optional previous messages.
        max_history: Maximum number of history messages to include.

    Returns:
        List of messages for the LLM.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Add conversation history if provided (last N messages)
    if conversation_history:
        messages.extend(conversation_history[-max_history:])

    # Add current query with context
    messages.append({"role": "user", "content": build_user_message(query, context)})

    return messages
