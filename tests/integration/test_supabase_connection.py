import pytest

from pliris.database.postgres import close_postgres_pool, postgres_connection
from pliris.database.supabase_client import get_supabase_admin_client

pytestmark = pytest.mark.integration


def test_documents_table_is_reachable_through_data_api() -> None:
    client = get_supabase_admin_client()
    response = client.table("documents").select("id").limit(1).execute()
    assert response.data is not None


def test_postgres_session_pooler_connection() -> None:
    try:
        with postgres_connection() as connection, connection.cursor() as cursor:
            cursor.execute("select 1 as ok")
            row = cursor.fetchone()
            assert row["ok"] == 1
    finally:
        close_postgres_pool()


def test_hybrid_search_function_exists() -> None:
    try:
        with postgres_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    select exists (
                        select 1
                        from pg_proc p
                        join pg_namespace n on n.oid = p.pronamespace
                        where n.nspname = 'public'
                          and p.proname = 'hybrid_search'
                    ) as exists
                    """
            )
            row = cursor.fetchone()
            assert row["exists"] is True
    finally:
        close_postgres_pool()
