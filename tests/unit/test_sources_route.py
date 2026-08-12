from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.developer_access import require_developer_access
from api.routes.sources import get_document_repository, router


class FakeRepository:
    def __init__(self) -> None:
        self.document_id = uuid4()
        self.now = datetime.now(UTC)

    def summary(self) -> dict:
        return {
            "id": self.document_id,
            "manifest_id": "babok-v3",
            "title": "BABOK Guide",
            "source_filename": "BABOK.pdf",
            "author": "IIBA",
            "source_type": "book",
            "access": "private",
            "status": "ready",
            "page_count": 500,
            "chunk_count": 10,
            "total_tokens": 5000,
            "last_ingested_at": self.now,
            "created_at": self.now,
            "updated_at": self.now,
        }

    async def list_documents(self, **_: object):
        return [self.summary()], 1

    async def get_stats(self) -> dict:
        return {
            "total_documents": 1,
            "total_chunks": 10,
            "total_pages": 500,
            "total_tokens": 5000,
            "ready_documents": 1,
            "pending_documents": 0,
            "processing_documents": 0,
            "failed_documents": 0,
            "archived_documents": 0,
            "last_ingested_at": self.now,
        }

    async def get_by_id(self, document_id: UUID):
        if document_id != self.document_id:
            return None
        return {
            **self.summary(),
            "edition": "Version 3",
            "publication_year": 2015,
            "mime_type": "application/pdf",
            "checksum_sha256": "a" * 64,
            "metadata": {"source_type": "book"},
            "has_ingestion_error": False,
        }

    async def list_chunks(self, document_id: UUID, **_: object):
        return [
            {
                "id": uuid4(),
                "chunk_index": 0,
                "content": "Grounded source content",
                "page_start": 1,
                "page_end": 1,
                "chapter": None,
                "section": "Introduction",
                "heading_path": ["Introduction"],
                "token_count": 20,
                "content_hash": "b" * 64,
                "embedding_model": "text-embedding-3-small",
                "created_at": self.now,
                "updated_at": self.now,
            }
        ], 1


def _client() -> tuple[TestClient, FakeRepository]:
    fake = FakeRepository()
    app = FastAPI()
    app.include_router(router, prefix="/api/sources")
    app.dependency_overrides[require_developer_access] = lambda: None
    app.dependency_overrides[get_document_repository] = lambda: fake
    return TestClient(app), fake


def test_source_routes_return_safe_views() -> None:
    client, repository = _client()
    assert client.get("/api/sources/").status_code == 200
    assert client.get("/api/sources/stats").status_code == 200
    detail = client.get(f"/api/sources/{repository.document_id}")
    assert detail.status_code == 200
    assert "storage_path" not in detail.json()
    assert "ingestion_error" not in detail.json()
    chunks = client.get(f"/api/sources/{repository.document_id}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()["items"][0]["content"] == "Grounded source content"


def test_unknown_source_returns_404() -> None:
    client, _ = _client()
    unknown = uuid4()
    assert client.get(f"/api/sources/{unknown}").status_code == 404
    assert client.get(f"/api/sources/{unknown}/chunks").status_code == 404
