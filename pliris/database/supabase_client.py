from functools import lru_cache

from supabase.client import ClientOptions

from pliris.config.settings import get_settings
from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    """
    Create the server-side Supabase client.

    This client uses SUPABASE_SECRET_KEY and must never be imported into
    browser-executed code or exposed to the Streamlit frontend.
    """
    settings = get_settings()

    return create_client(
        settings.supabase_url_string,
        settings.supabase_secret_key.get_secret_value(),
        options=ClientOptions(
            postgrest_client_timeout=settings.postgres_connect_timeout_seconds,
            storage_client_timeout=settings.postgres_connect_timeout_seconds,
            schema="public",
        ),
    )


@lru_cache(maxsize=1)
def get_supabase_public_client() -> Client:
    """
    Create a low-privilege client for negative permission tests.

    The initial Pliris release does not query knowledge-base tables directly
    from the browser. This client exists only to verify that public access is
    blocked as intended.
    """
    settings = get_settings()

    return create_client(
        settings.supabase_url_string,
        settings.supabase_publishable_key.get_secret_value(),
        options=ClientOptions(
            postgrest_client_timeout=settings.postgres_connect_timeout_seconds,
            storage_client_timeout=settings.postgres_connect_timeout_seconds,
            schema="public",
        ),
    )


@lru_cache(maxsize=1)
def get_client() -> Client:
    """
    Return the server-side Supabase administrative client.

    Compatibility accessor for existing retrieval modules.
    New backend code should prefer get_supabase_admin_client().
    """
    return get_supabase_admin_client()
