from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.developer_access import (
    DEVELOPER_KEY_HEADER,
    get_expected_developer_key,
    require_developer_access,
)
from api.routes.source_staging import (
    get_pdf_staging_manifest,
    get_pdf_staging_max_bytes,
    get_pdf_staging_repository,
    get_pdf_staging_storage,
    router,
)
from ingestion.models import DocumentManifestEntry


class FakeRepository:
    def __init__(self) -> None:
        self.existing_checksum: dict | None = None
        self.existing_manifest: dict | None = None
        self.created: dict[str, object] | None = None

    def get_document_by_checksum(self, _: str) -> dict | None:
        return self.existing_checksum

    def get_document(self, _: str) -> dict | None:
        return self.existing_manifest

    def create_pending_document(self, **values: object):
        self.created = values
        return uuid4()


class FakeStorage:
    bucket = "knowledge-base"

    def __init__(self) -> None:
        self.uploaded = False
        self.removed: list[str] = []

    def upload_pdf_bytes(
        self,
        _: bytes,
        *,
        document_id: str,
        filename: str,
    ) -> str:
        self.uploaded = True
        return f"{document_id}/{filename}"

    def remove(self, storage_path: str) -> None:
        self.removed.append(storage_path)


def _manifest(
    *,
    document_id: str = "gao-agile-assessment-guide-2023",
    source_filename: str = "GAO_Agile_Assessment_Guide_2023.pdf",
) -> DocumentManifestEntry:
    return DocumentManifestEntry(
        document_id=document_id,
        title="GAO Agile Assessment Guide",
        source_filename=source_filename,
        publication_year=2023,
        source_type="government-guide",
        access="public",
    )


def _client(
    manifest: DocumentManifestEntry | None = None,
) -> tuple[TestClient, FakeRepository, FakeStorage]:
    repository = FakeRepository()
    storage = FakeStorage()
    app = FastAPI()
    app.include_router(router, prefix="/api/sources")
    app.dependency_overrides[require_developer_access] = lambda: None
    if manifest is not None:
        app.dependency_overrides[get_pdf_staging_manifest] = lambda: manifest
    app.dependency_overrides[get_pdf_staging_repository] = lambda: repository
    app.dependency_overrides[get_pdf_staging_storage] = lambda: storage
    app.dependency_overrides[get_pdf_staging_max_bytes] = lambda: 1024
    return TestClient(app), repository, storage


def _upload(
    client: TestClient,
    *,
    filename: str = "GAO_Agile_Assessment_Guide_2023.pdf",
    payload: bytes = b"%PDF-1.7\ncontrolled-acceptance-content",
):
    return client.post(
        "/api/sources/stage",
        data={"manifest_id": "gao-agile-assessment-guide-2023"},
        files={"upload": (filename, payload, "application/pdf")},
    )


def test_stage_route_creates_safe_pending_response() -> None:
    client, repository, storage = _client()

    response = _upload(client)

    assert response.status_code == 201
    assert response.json()["manifest_id"] == "gao-agile-assessment-guide-2023"
    assert response.json()["status"] == "pending"
    assert response.json()["size_bytes"] > 0
    assert "storage_path" not in response.json()
    assert "storage_bucket" not in response.json()
    assert repository.created is not None
    assert storage.uploaded is True


def test_stage_route_rejects_duplicate_before_upload() -> None:
    client, repository, storage = _client()
    repository.existing_checksum = {"manifest_id": "existing-source"}

    response = _upload(client)

    assert response.status_code == 409
    assert storage.uploaded is False
    assert repository.created is None


def test_stage_route_rejects_protected_babok_before_side_effects() -> None:
    client, repository, storage = _client(
        _manifest(
            document_id="babok-v3",
            source_filename="BABOK_Guide_v3_Member.pdf",
        )
    )

    response = _upload(client, filename="BABOK_Guide_v3_Member.pdf")

    assert response.status_code == 403
    assert storage.uploaded is False
    assert repository.created is None


def test_stage_route_rejects_invalid_pdf_without_side_effects() -> None:
    client, repository, storage = _client()

    response = _upload(client, payload=b"not-a-pdf")

    assert response.status_code == 422
    assert storage.uploaded is False
    assert repository.created is None


def test_stage_route_requires_developer_access() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/sources")
    app.dependency_overrides[get_expected_developer_key] = lambda: "developer-secret"
    client = TestClient(app)

    response = _upload(client)

    assert response.status_code == 401

    wrong_key_response = client.post(
        "/api/sources/stage",
        headers={DEVELOPER_KEY_HEADER: "wrong-secret"},
        data={"manifest_id": "gao-agile-assessment-guide-2023"},
        files={
            "upload": (
                "GAO_Agile_Assessment_Guide_2023.pdf",
                b"%PDF-1.7\ncontrolled-acceptance-content",
                "application/pdf",
            )
        },
    )
    assert wrong_key_response.status_code == 401
