from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from ingestion.models import IngestionSummary
from scripts.ingest_document import main


def test_cli_passes_staged_document_id_to_pipeline() -> None:
    staged_document_id = uuid4()
    pipeline = MagicMock()
    pipeline.ingest.return_value = IngestionSummary(
        document_id="staged-guide",
        database_document_id=str(staged_document_id),
        status="completed",
        source_path="data/private/staged-guide.pdf",
        storage_path="staged-guide/staged-guide.pdf",
        page_count=1,
        chunk_count=1,
        estimated_embedding_tokens=17,
        warnings=[],
    )

    with (
        patch.object(
            sys,
            "argv",
            [
                "ingest_document.py",
                "--document-id",
                "staged-guide",
                "--staged-document-id",
                str(staged_document_id),
            ],
        ),
        patch(
            "scripts.ingest_document.IngestionPipeline",
            return_value=pipeline,
        ),
        patch("scripts.ingest_document.close_postgres_pool") as close_pool,
    ):
        result = main()

    assert result == 0
    pipeline.ingest.assert_called_once_with(
        "staged-guide",
        dry_run=False,
        max_pages=None,
        force=False,
        staged_document_id=staged_document_id,
        embedding_batch_size=64,
    )
    close_pool.assert_called_once_with()


def test_cli_rejects_force_with_staged_document_id() -> None:
    staged_document_id = uuid4()

    with (
        patch.object(
            sys,
            "argv",
            [
                "ingest_document.py",
                "--document-id",
                "staged-guide",
                "--staged-document-id",
                str(staged_document_id),
                "--force",
            ],
        ),
        patch("scripts.ingest_document.IngestionPipeline") as pipeline_factory,
        patch("scripts.ingest_document.close_postgres_pool") as close_pool,
        pytest.raises(SystemExit) as error,
    ):
        main()

    assert error.value.code == 2
    pipeline_factory.assert_not_called()
    close_pool.assert_not_called()
