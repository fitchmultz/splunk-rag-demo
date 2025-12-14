"""Embedding generation using Ollama."""

from collections.abc import Callable

import numpy as np
import ollama

from splunkbot.config import settings


def embed_texts(
    texts: list[str],
    batch_size: int = 32,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[np.ndarray]:
    """Generate embeddings for a list of texts using Ollama.

    Args:
        texts: List of texts to embed.
        batch_size: Number of texts to embed at once.
        progress_callback: Optional callback(completed, total) for progress updates.

    Returns:
        List of embedding vectors as numpy arrays.
    """
    embeddings: list[np.ndarray] = []
    total = len(texts)

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = _embed_batch(batch)
        embeddings.extend(batch_embeddings)

        if progress_callback:
            progress_callback(len(embeddings), total)

    return embeddings


def _embed_batch(texts: list[str]) -> list[np.ndarray]:
    """Embed a batch of texts.

    Args:
        texts: List of texts to embed.

    Returns:
        List of embedding vectors.
    """
    client = ollama.Client(host=settings.ollama_host)

    # Ollama embed API accepts a list of inputs
    response = client.embed(
        model=settings.embedding_model,
        input=texts,
    )

    # Convert to numpy arrays
    return [np.array(emb, dtype=np.float32) for emb in response["embeddings"]]


def embed_single(text: str) -> np.ndarray:
    """Generate embedding for a single text.

    Args:
        text: Text to embed.

    Returns:
        Embedding vector as numpy array.
    """
    client = ollama.Client(host=settings.ollama_host)

    response = client.embed(
        model=settings.embedding_model,
        input=text,
    )

    return np.array(response["embeddings"][0], dtype=np.float32)


async def embed_texts_async(texts: list[str], batch_size: int = 32) -> list[np.ndarray]:
    """Generate embeddings asynchronously.

    Note: Ollama Python client doesn't have native async support,
    so this runs the sync version. For true async, use httpx directly.

    Args:
        texts: List of texts to embed.
        batch_size: Number of texts to embed at once.

    Returns:
        List of embedding vectors.
    """
    # For now, use the sync version
    # In a production app, you might use httpx with async
    return embed_texts(texts, batch_size)
