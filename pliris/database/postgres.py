from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from pliris.config.settings import get_settings


@lru_cache(maxsize=1)
def get_postgres_pool() -> ConnectionPool:
    """Create a lazy connection pool for the hosted Supabase Session Pooler."""
    settings = get_settings()

    return ConnectionPool(
        conninfo=settings.supabase_db_url.get_secret_value(),
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        timeout=settings.postgres_connect_timeout_seconds,
        open=False,
        kwargs={
            "row_factory": dict_row,
            "connect_timeout": settings.postgres_connect_timeout_seconds,
            "application_name": "pliris-ba-bot",
        },
    )


def open_postgres_pool() -> ConnectionPool:
    """Open the shared pool and wait until at least one connection is usable."""
    pool = get_postgres_pool()
    if pool.closed:
        pool.open(wait=True)
    return pool


def close_postgres_pool() -> None:
    """Close and discard the shared connection pool."""
    pool = get_postgres_pool()

    if not pool.closed:
        pool.close()

    # A closed Psycopg pool cannot be reopened.
    # Clearing the cache allows the next call to create a fresh pool.
    get_postgres_pool.cache_clear()


@contextmanager
def postgres_connection() -> Iterator[Connection]:
    """Yield one pooled PostgreSQL connection."""
    pool = open_postgres_pool()
    with pool.connection() as connection:
        yield connection
