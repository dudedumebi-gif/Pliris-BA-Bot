from __future__ import annotations

import uuid
from pathlib import Path

import fitz
import pytest

from ingestion.embedding_service import EmbeddingService
from ingestion.pipeline import IngestionPipeline
from ingestion.repository import IngestionRepository
from ingestion.storage_service import KnowledgeBaseStorage
from pliris.config.settings import get_settings
from pliris.database.postgres import close_postgres_pool
from pliris.database.supabase_client import get_supabase_admin_client

pytestmark = pytest.mark.integration


def _create_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "BUSINESS ANALYSIS INTEGRATION TEST\n\n"
            "A requirements traceability matrix connects requirements to design, "
            "development, testing, and business objectives."
        ),
    )
    document.save(path)
    document.close()


def test_one_document_ingestion_is_idempotent(tmp_path: Path) -> None:
    unique_id = f"phase2-{uuid.uuid4().hex[:12]}"
    pdf_path = tmp_path / "sample.pdf"
    manifest_path = tmp_path / "manifest.yaml"
    _create_pdf(pdf_path)

    manifest_path.write_text(
        f"""
version: 1
documents:
  - document_id: {unique_id}
    title: Phase 2 Integration Test
    source_filename: sample.pdf
    access: private
    include_in_public_repository: false
    enabled: true
""".strip(),
        encoding="utf-8",
    )

    repository = IngestionRepository()
    storage = KnowledgeBaseStorage()
    pipeline = IngestionPipeline(
        manifest_path=manifest_path,
        private_directory=tmp_path,
        repository=repository,
        storage=storage,
    )

    storage_path = storage.build_storage_path(unique_id, pdf_path.name)

    try:
        first = pipeline.ingest(unique_id)
        assert first.status == "completed"
        assert first.chunk_count > 0

        second = pipeline.ingest(unique_id)
        assert second.status == "skipped"

        query = "What does a requirements traceability matrix connect?"
        query_embedding = EmbeddingService().embed_texts([query]).embeddings[0]
        client = get_supabase_admin_client()
        response = client.rpc(
            "hybrid_search",
            {
                "query_text": query,
                "query_embedding": query_embedding,
                "match_count": 3,
                "full_text_weight": 1.0,
                "semantic_weight": 1.0,
                "rrf_k": get_settings().rrf_k,
                "filter_document_ids": [first.database_document_id],
            },
        ).execute()

        assert response.data
        assert response.data[0]["document_title"] == "Phase 2 Integration Test"
        assert response.data[0]["page_start"] == 1

    finally:
        repository.delete_document(unique_id)
        try:
            storage.remove(storage_path)
        finally:
            close_postgres_pool()
