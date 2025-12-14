"""Database connection pool management using asyncpg."""

import asyncpg
from pgvector.asyncpg import register_vector

from splunkbot.config import settings

# Global connection pool
_pool: asyncpg.Pool | None = None
_pool_with_vector: bool = False


async def get_pool(with_vector: bool = True) -> asyncpg.Pool:
    """Get or create the database connection pool.

    Args:
        with_vector: If True, register pgvector types on connections.
                     Set to False for schema initialization before pgvector exists.

    Returns:
        asyncpg.Pool: The database connection pool.
    """
    global _pool, _pool_with_vector

    # If we need vector but pool was created without it, close and recreate
    if _pool is not None and with_vector and not _pool_with_vector:
        await _pool.close()
        _pool = None

    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password,
            database=settings.postgres_db,
            min_size=2,
            max_size=10,
            init=_init_connection if with_vector else None,
        )
        _pool_with_vector = with_vector

    return _pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Initialize each connection with pgvector support.

    Args:
        conn: The connection to initialize.
    """
    await register_vector(conn)


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_connection() -> asyncpg.Connection:
    """Get a single connection from the pool.

    Returns:
        asyncpg.Connection: A database connection.
    """
    pool = await get_pool()
    return await pool.acquire()
