from __future__ import annotations

from uuid import uuid4

import pytest

from pliris.database.postgres import (
    close_postgres_pool,
    postgres_connection,
)
from pliris.database.repositories.grounded_persistence import (
    GroundedExchange,
    GroundedPersistenceRepository,
)
from pliris.retrieval.models import RetrievedChunk

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_grounded_exchange_persists_transactionally() -> None:
    session_id = f"integration-{uuid4()}"
    outcome = None

    with postgres_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                select
                    dc.id as chunk_id,
                    dc.document_id,
                    dc.content,
                    dc.page_start,
                    dc.page_end,
                    d.title,
                    dc.metadata
                from public.document_chunks dc
                join public.documents d
                  on d.id = dc.document_id
                where d.status = 'ready'
                order by dc.created_at
                limit 1
                """
        )
        row = cursor.fetchone()

    if not row:
        close_postgres_pool()
        pytest.skip("No ready document chunk is available.")

    chunk = RetrievedChunk(
        rank=1,
        chunk_id=str(row["chunk_id"]),
        text=row["content"],
        title=row["title"],
        source="integration-source",
        page_start=row["page_start"],
        page_end=row["page_end"],
        score=0.01,
        document_id=str(row["document_id"]),
        metadata={
            **dict(row["metadata"] or {}),
            "semantic_rank": 1,
            "keyword_rank": 2,
        },
    )

    repository = GroundedPersistenceRepository()

    try:
        outcome = await repository.persist_exchange(
            GroundedExchange(
                client_session_id=session_id,
                user_id="integration-user",
                original_query="Integration persistence question",
                assistant_response=("Integration persistence answer [S1]."),
                scope_status="in_scope",
                scope_confidence=None,
                scope_category="business_analysis",
                citations=(
                    {
                        "citation_id": "S1",
                        "chunk_id": chunk.chunk_id,
                        "source": chunk.source,
                    },
                ),
                model_name="integration-model",
                input_tokens=10,
                output_tokens=5,
                total_latency_ms=100,
                retrieval_latency_ms=25,
                requested_match_count=1,
                chunks=(chunk,),
                selected_chunk_ids=frozenset({chunk.chunk_id}),
                insufficient_evidence=False,
                response_id="integration-response",
                metadata={"test_run": True},
            )
        )

        with postgres_connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                    select client_session_id
                    from public.conversations
                    where id = %s
                    """,
                (outcome.database_conversation_id,),
            )
            conversation = cursor.fetchone()

            cursor.execute(
                """
                    select role, content, model_name
                    from public.messages
                    where id in (%s, %s)
                    order by
                        case when id = %s then 0 else 1 end
                    """,
                (
                    outcome.user_message_id,
                    outcome.assistant_message_id,
                    outcome.user_message_id,
                ),
            )
            messages = cursor.fetchall()

            cursor.execute(
                """
                    select
                        scope_confidence,
                        retrieval_method,
                        requested_match_count
                    from public.retrieval_queries
                    where id = %s
                    """,
                (outcome.retrieval_query_id,),
            )
            retrieval_query = cursor.fetchone()

            cursor.execute(
                """
                    select
                        result_rank,
                        semantic_rank,
                        keyword_rank,
                        selected_for_context
                    from public.retrieval_results
                    where retrieval_query_id = %s
                    """,
                (outcome.retrieval_query_id,),
            )
            retrieval_result = cursor.fetchone()

            cursor.execute(
                """
                    select event_type, properties
                    from public.monitoring_events
                    where id = %s
                    """,
                (outcome.monitoring_event_id,),
            )
            event = cursor.fetchone()

        assert conversation["client_session_id"] == session_id
        assert [message["role"] for message in messages] == [
            "user",
            "assistant",
        ]
        assert messages[1]["model_name"] == "integration-model"
        assert retrieval_query["scope_confidence"] == 1.0
        assert retrieval_query["retrieval_method"] == ("hosted_hybrid_rrf")
        assert retrieval_query["requested_match_count"] == 1
        assert retrieval_result["result_rank"] == 1
        assert retrieval_result["semantic_rank"] == 1
        assert retrieval_result["keyword_rank"] == 2
        assert retrieval_result["selected_for_context"] is True
        assert event["event_type"] == ("grounded_response_completed")
        assert event["properties"]["test_run"] is True

    finally:
        if outcome is not None:
            with postgres_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        delete from public.monitoring_events
                        where id = %s
                        """,
                        (outcome.monitoring_event_id,),
                    )
                    cursor.execute(
                        """
                        delete from public.retrieval_queries
                        where id = %s
                        """,
                        (outcome.retrieval_query_id,),
                    )
                    cursor.execute(
                        """
                        delete from public.conversations
                        where id = %s
                        """,
                        (outcome.database_conversation_id,),
                    )
                connection.commit()

        close_postgres_pool()
