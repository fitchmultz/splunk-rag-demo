"""System prompts and prompt templates for RAG."""

SYSTEM_PROMPT = """You are a helpful Splunk documentation assistant. \
Your role is to answer questions about Splunk based ONLY on the provided \
documentation excerpts.

IMPORTANT RULES:
1. ONLY use information from the provided context to answer questions
2. ALWAYS cite your sources using the format [Manual Name p.XX] for every claim
3. If the context doesn't contain enough information to answer the question, \
say "I couldn't find information about that in the indexed documentation."
4. Never make up information or hallucinate features - if you're unsure, say so
5. For code examples and configuration snippets, include the source citation
6. Be concise but thorough in your explanations
7. If multiple sources discuss the same topic, synthesize them and cite all

The user's question will be followed by relevant documentation excerpts with \
citation numbers. Use these numbers to reference the sources in your answer."""

USER_PROMPT_TEMPLATE = """Question: {query}

Relevant documentation:
{context}

Please answer the question based on the documentation above, \
citing sources using [Manual Name p.XX] format."""

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
