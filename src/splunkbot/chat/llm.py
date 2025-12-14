"""Ollama LLM client for chat completions."""

from dataclasses import dataclass
from typing import Literal

import ollama

from splunkbot.config import settings

# Type for think parameter matching Ollama's API
ThinkLevel = bool | Literal["low", "medium", "high"] | None


@dataclass
class ChatResponse:
    """Response from chat completion."""

    content: str
    thinking: str | None = None


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    think: ThinkLevel = "medium",
) -> ChatResponse:
    """Send a chat completion request to Ollama.

    Args:
        messages: List of message dicts with 'role' and 'content'.
        model: Model to use. Defaults to settings.chat_model.
        temperature: Sampling temperature.
        think: Enable thinking. For gpt-oss use "low"/"medium"/"high".

    Returns:
        ChatResponse with content and optional thinking.
    """
    model = model or settings.chat_model
    client = ollama.Client(host=settings.ollama_host)

    response = client.chat(
        model=model,
        messages=messages,
        options={"temperature": temperature},
        think=think,
    )

    thinking = None
    if hasattr(response.message, "thinking"):
        thinking = response.message.thinking
    elif isinstance(response, dict) and "message" in response:
        thinking = response["message"].get("thinking")

    if hasattr(response.message, "content"):
        content = response.message.content
    else:
        content = response["message"]["content"]

    return ChatResponse(content=content or "", thinking=thinking)


@dataclass
class StreamChunk:
    """A chunk from streaming response."""

    content: str | None = None
    thinking: str | None = None
    is_thinking: bool = False


def chat_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    think: ThinkLevel = "medium",
):
    """Stream a chat completion response from Ollama.

    Args:
        messages: List of message dicts with 'role' and 'content'.
        model: Model to use. Defaults to settings.chat_model.
        temperature: Sampling temperature.
        think: Enable thinking. For gpt-oss use "low"/"medium"/"high".

    Yields:
        StreamChunk with either thinking or content.
    """
    model = model or settings.chat_model
    client = ollama.Client(host=settings.ollama_host)

    for chunk in client.chat(
        model=model,
        messages=messages,
        options={"temperature": temperature},
        think=think,
        stream=True,
    ):
        if hasattr(chunk, "message"):
            msg = chunk.message
            thinking = getattr(msg, "thinking", None)
            content = getattr(msg, "content", None)
        elif isinstance(chunk, dict) and "message" in chunk:
            msg = chunk["message"]
            thinking = msg.get("thinking")
            content = msg.get("content")
        else:
            continue

        if thinking:
            yield StreamChunk(thinking=thinking, is_thinking=True)
        if content:
            yield StreamChunk(content=content, is_thinking=False)


def check_model_available(model: str | None = None) -> tuple[bool, str | None]:
    """Check if a model is available in Ollama.

    Args:
        model: Model name to check. Defaults to settings.chat_model.

    Returns:
        Tuple of (is_available, error_message). Error is None if available.
    """
    model = model or settings.chat_model
    client = ollama.Client(host=settings.ollama_host)

    try:
        models = client.list()
        available = [m["name"] for m in models.get("models", [])]
        # Check both exact match and without tag
        is_available = model in available or any(
            m.startswith(model.split(":")[0]) for m in available
        )
        if is_available:
            return True, None
        return False, f"Model '{model}' not found. Available: {', '.join(available[:5])}"
    except Exception as e:
        return False, f"Could not connect to Ollama: {e}"


def list_models() -> tuple[list[str], str | None]:
    """List all available models in Ollama.

    Returns:
        Tuple of (model_names, error_message). Error is None if successful.
    """
    client = ollama.Client(host=settings.ollama_host)

    try:
        models = client.list()
        return [m["name"] for m in models.get("models", [])], None
    except Exception as e:
        return [], f"Could not connect to Ollama: {e}"
