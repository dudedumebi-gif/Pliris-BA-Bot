import hashlib
import sys
import uuid
from dataclasses import dataclass
from typing import Any

from pliris.config.settings import get_settings
from pliris.database.postgres import close_postgres_pool, postgres_connection
from pliris.database.supabase_client import (
    get_supabase_admin_client,
    get_supabase_public_client,
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_check(name: str, operation: Any) -> CheckResult:
    try:
        detail = operation()
        return CheckResult(name=name, passed=True, detail=str(detail))
    except Exception as exc:
        return CheckResult(
            name=name,
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )


def check_data_api() -> str:
    client = get_supabase_admin_client()
    response = client.table("documents").select("id").limit(1).execute()
    count = len(response.data or [])
    return f"documents table reachable; returned {count} row(s)"


def check_storage() -> str:
    settings = get_settings()
    client = get_supabase_admin_client()
    entries = client.storage.from_(settings.supabase_storage_bucket).list()
    return (
        f"private bucket '{settings.supabase_storage_bucket}' reachable; "
        f"{len(entries or [])} root item(s)"
    )


def check_database_objects() -> str:
    expected_tables = {
        "documents",
        "document_chunks",
        "ingestion_runs",
        "conversations",
        "messages",
        "retrieval_queries",
        "retrieval_results",
        "user_feedback",
        "monitoring_events",
    }

    with postgres_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                  and table_name = any(%s)
                """,
            (list(expected_tables),),
        )
        actual_tables = {row["table_name"] for row in cursor.fetchall()}

        cursor.execute(
            """
                select exists (
                    select 1
                    from pg_extension
                    where extname = 'vector'
                ) as vector_ok
                """
        )
        vector_ok = bool(cursor.fetchone()["vector_ok"])

        cursor.execute(
            """
                select exists (
                    select 1
                    from pg_proc p
                    join pg_namespace n on n.oid = p.pronamespace
                    where n.nspname = 'public'
                      and p.proname = 'hybrid_search'
                ) as hybrid_search_ok
                """
        )
        hybrid_search_ok = bool(cursor.fetchone()["hybrid_search_ok"])

    missing = expected_tables - actual_tables
    if missing:
        raise RuntimeError(f"Missing tables: {sorted(missing)}")
    if not vector_ok:
        raise RuntimeError("The vector extension is not enabled.")
    if not hybrid_search_ok:
        raise RuntimeError("The public.hybrid_search function is missing.")

    return "9 core tables, vector extension, and hybrid_search function verified"


def check_public_access_is_blocked() -> str:
    client = get_supabase_public_client()
    try:
        response = client.table("documents").select("id").limit(1).execute()
    except Exception:
        return "publishable-key access is blocked as intended"

    if response.data:
        raise RuntimeError(
            "Publishable-key client read rows from documents; review grants and RLS."
        )

    return (
        "publishable-key query returned no rows. Access appears restricted, "
        "but review Supabase API logs if a strict permission error is required."
    )


def check_write_and_hybrid_search() -> str:
    settings = get_settings()
    test_id = uuid.uuid4()
    checksum = hashlib.sha256(str(test_id).encode()).hexdigest()
    content_hash = hashlib.sha256(f"chunk-{test_id}".encode()).hexdigest()

    vector = [0.0] * settings.openai_embedding_dimensions
    vector[0] = 1.0
    vector_literal = "[" + ",".join(str(value) for value in vector) + "]"

    document_id: str | None = None

    try:
        with postgres_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    insert into public.documents (
                        title,
                        source_filename,
                        checksum_sha256,
                        status,
                        metadata
                    )
                    values (%s, %s, %s, 'ready', %s::jsonb)
                    returning id
                    """,
                    (
                        f"Pliris integration check {test_id}",
                        f"integration-check-{test_id}.pdf",
                        checksum,
                        '{"temporary": true, "source": "integration_check"}',
                    ),
                )
                document_id = str(cursor.fetchone()["id"])

                cursor.execute(
                    """
                    insert into public.document_chunks (
                        document_id,
                        chunk_index,
                        content,
                        page_start,
                        page_end,
                        chapter,
                        section,
                        token_count,
                        content_hash,
                        embedding,
                        embedding_model,
                        embedding_dimensions,
                        metadata
                    )
                    values (
                        %s::uuid,
                        0,
                        %s,
                        1,
                        1,
                        'Integration',
                        'Supabase',
                        10,
                        %s,
                        %s::vector,
                        %s,
                        %s,
                        %s::jsonb
                    )
                    """,
                    (
                        document_id,
                        "Business analysis integration verification test content.",
                        content_hash,
                        vector_literal,
                        settings.openai_embedding_model,
                        settings.openai_embedding_dimensions,
                        '{"temporary": true}',
                    ),
                )
            connection.commit()

        admin = get_supabase_admin_client()
        rpc_response = admin.rpc(
            "hybrid_search",
            {
                "query_text": "business analysis integration verification",
                "query_embedding": vector,
                "match_count": 5,
                "full_text_weight": 1.0,
                "semantic_weight": 1.0,
                "rrf_k": settings.rrf_k,
                "filter_document_ids": [document_id],
            },
        ).execute()

        rows = rpc_response.data or []
        if not rows:
            raise RuntimeError("hybrid_search returned no test result.")

        if str(rows[0]["document_id"]) != document_id:
            raise RuntimeError("hybrid_search returned an unexpected document.")

        return "temporary insert, FTS trigger, pgvector, and hybrid_search RPC succeeded"

    finally:
        if document_id is not None:
            with postgres_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "delete from public.documents where id = %s::uuid",
                        (document_id,),
                    )
                connection.commit()


def main() -> int:
    checks = [
        ("Supabase Data API", check_data_api),
        ("Private Storage bucket", check_storage),
        ("Database schema", check_database_objects),
        ("Public access restriction", check_public_access_is_blocked),
        ("Write + hybrid retrieval", check_write_and_hybrid_search),
    ]

    results: list[CheckResult] = []
    try:
        for name, operation in checks:
            result = run_check(name, operation)
            results.append(result)
            marker = "PASS" if result.passed else "FAIL"
            print(f"[{marker}] {result.name}: {result.detail}")
    finally:
        close_postgres_pool()

    failures = [result for result in results if not result.passed]
    if failures:
        print(f"\nSupabase integration failed {len(failures)} check(s).")
        return 1

    print("\nSupabase integration passed all checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
